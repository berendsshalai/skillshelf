from __future__ import annotations

from collections.abc import Callable
from typing import Any, cast

from agents import FunctionTool, function_tool

from .filesystem import RepositoryFilesystem
from .subprocess import SafeCommandExecutor, SafeCommandRequest
from ..runtime.evidence import RunEvidenceRecorder, execute_recorded

ToolBuilder = Callable[[], list[FunctionTool]]


class CapabilityToolRegistry:
    """Maps declared capability identifiers to concrete Agents SDK tools."""

    def __init__(self, *, filesystem: RepositoryFilesystem, commands: SafeCommandExecutor) -> None:
        self.filesystem = filesystem
        self.commands = commands
        self.evidence: RunEvidenceRecorder | None = None
        self.agent_id = "runtime"
        self._builders: dict[str, ToolBuilder] = {
            "read_files": self._read_tools,
            "read_skill_files": self._read_tools,
            "read_agent_events": self._read_tools,
            "search_sources": self._read_tools,
            "write_project_files": self._write_tools,
            "run_tests": self._command_tools,
            "run_frontend_tests": self._command_tools,
            "run_evaluations": self._command_tools,
            "run_safe_commands": self._command_tools,
            "inspect_git": self._command_tools,
        }

    def bind_evidence(self, recorder: RunEvidenceRecorder, *, agent_id: str = "runtime") -> None:
        self.evidence = recorder
        self.agent_id = agent_id

    def _recorded(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        invoke: Callable[[], Any],
    ) -> Any:
        return execute_recorded(
            self.evidence,
            agent_id=self.agent_id,
            tool_name=tool_name,
            arguments=arguments,
            invoke=invoke,
        )

    def build(self, capabilities: list[str]) -> list[FunctionTool]:
        result: list[FunctionTool] = []
        seen: set[str] = set()
        for capability in capabilities:
            try:
                tools = self._builders[capability]()
            except KeyError as exc:
                raise KeyError(f"no operational tool builder for capability {capability!r}") from exc
            for tool in tools:
                if tool.name not in seen:
                    seen.add(tool.name)
                    result.append(tool)
        return result

    def supports(self, capability: str) -> bool:
        return capability in self._builders

    def _read_tools(self) -> list[FunctionTool]:
        filesystem = self.filesystem

        def read_text_file(path: str) -> dict[str, Any]:
            """Read a UTF-8 text file within the authorised repository."""
            return self._recorded(
                "read_text_file",
                {"path": path},
                lambda: cast(dict[str, Any], filesystem.read_text_file(path).model_dump()),
            )

        def read_binary_metadata(path: str) -> dict[str, Any]:
            """Return size and SHA-256 for a repository file without returning its bytes."""
            return self._recorded(
                "read_binary_metadata",
                {"path": path},
                lambda: cast(
                    dict[str, Any], filesystem.read_binary_metadata(path).model_dump()
                ),
            )

        def list_directory(path: str = ".") -> list[str]:
            """List direct children of a repository directory."""
            return self._recorded(
                "list_directory",
                {"path": path},
                lambda: cast(list[str], filesystem.list_directory(path)),
            )

        def search_text(query: str, path: str = ".", max_results: int = 100) -> list[dict[str, Any]]:
            """Search UTF-8 repository files and return bounded matching lines."""
            return self._recorded(
                "search_text",
                {"query": query, "path": path, "max_results": max_results},
                lambda: cast(
                    list[dict[str, Any]],
                    [item.model_dump() for item in filesystem.search_text(query, path, max_results)],
                ),
            )

        return [
            function_tool(read_text_file),
            function_tool(read_binary_metadata),
            function_tool(list_directory),
            function_tool(search_text),
        ]

    def _write_tools(self) -> list[FunctionTool]:
        filesystem = self.filesystem

        def write_text_file(path: str, content: str) -> dict[str, Any]:
            """Atomically write repository text after approval and return before/after evidence."""
            return self._recorded(
                "write_text_file",
                {"path": path, "content": content},
                lambda: cast(dict[str, Any], filesystem.write_text_file(path, content).model_dump()),
            )

        def apply_unified_patch(patch: str) -> list[dict[str, Any]]:
            """Apply an approved Git unified patch confined to mutable repository paths."""
            return self._recorded(
                "apply_unified_patch",
                {"patch": patch},
                lambda: cast(
                    list[dict[str, Any]],
                    [item.model_dump() for item in filesystem.apply_unified_patch(patch)],
                ),
            )

        def create_directory(path: str) -> str:
            """Create an approved directory within mutable repository paths."""
            return self._recorded(
                "create_directory",
                {"path": path},
                lambda: cast(str, filesystem.create_directory(path)),
            )

        return [
            function_tool(write_text_file, needs_approval=True),
            function_tool(apply_unified_patch, needs_approval=True),
            function_tool(create_directory, needs_approval=True),
        ]

    def _command_tools(self) -> list[FunctionTool]:
        executor = self.commands

        def run_safe_command(request: SafeCommandRequest) -> dict[str, Any]:
            """Run one allowlisted executable with literal argv and no shell."""
            return self._recorded(
                "run_safe_command",
                {"request": request.model_dump(mode="json")},
                lambda: cast(dict[str, Any], executor.run(request).model_dump()),
            )

        return [function_tool(run_safe_command)]
