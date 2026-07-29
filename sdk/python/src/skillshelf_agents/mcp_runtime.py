from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, cast

import yaml

from .mcp import MCPManager
from .mcp import MCPServerDefinition as OperationalMCPServerDefinition

_LOCAL_TRANSPORTS = {"stdio", "streamable_http", "sse"}
_HOST_TRANSPORTS = {"host", "connector"}


@dataclass(frozen=True)
class MCPServerDefinition:
    """Compatibility view of one manifest entry.

    ``operational`` is populated only for transports the OpenAI Agents SDK can
    instantiate locally. Host and connector entries remain explicit adapters.
    """

    name: str
    transport: str
    read_tools: tuple[str, ...]
    write_tools: tuple[str, ...]
    confirmation_required: bool
    validation_command: str
    installation_status: str
    adapter: str | None
    secret_references: tuple[str, ...]
    required_by: tuple[str, ...]
    operational: OperationalMCPServerDefinition | None

    def required_for(self, agent_id: str) -> bool:
        if agent_id not in self.required_by:
            return False
        return "optional" not in self.installation_status.casefold()


class MCPRuntime:
    """Legacy policy/readiness facade backed by the operational MCP manager."""

    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        raw = yaml.safe_load((self.root / "mcp" / "registry.yml").read_text(encoding="utf-8"))
        self.manager = MCPManager()
        self.servers: dict[str, MCPServerDefinition] = {}
        self._tool_cache: dict[str, tuple[str, ...]] = {}
        self._connected = False
        self._connection_error: str | None = None
        self._run_managers: list[MCPManager] = []

        for item in raw["servers"]:
            definition = self._definition(item)
            if definition.name in self.servers:
                raise ValueError(f"duplicate MCP server name: {definition.name}")
            self.servers[definition.name] = definition
            if definition.operational is not None:
                self.manager.register(definition.operational)

    def _definition(self, item: dict[str, Any]) -> MCPServerDefinition:
        name = str(item["name"])
        transport = str(item["transport"])
        reads = tuple(str(tool) for tool in item.get("read_tools", ()))
        writes = tuple(str(tool) for tool in item.get("write_tools", ()))
        adapter = item.get("adapter")

        if transport in _HOST_TRANSPORTS:
            if adapter != "host-provided":
                raise ValueError(f"{name}: {transport} transport must declare adapter: host-provided")
            operational = None
        elif transport in _LOCAL_TRANSPORTS:
            if adapter is not None:
                raise ValueError(f"{name}: local SDK transport cannot declare a host adapter")
            env = self._resolve_environment(item.get("environment_references", ()))
            headers = self._resolve_headers(item.get("header_references", {}))
            cwd = item.get("cwd")
            if cwd is not None:
                cwd = str((self.root / str(cwd)).resolve())
            operational = OperationalMCPServerDefinition(
                name=name,
                transport=cast(
                    Literal["stdio", "streamable_http", "sse"],
                    transport,
                ),
                command=item.get("command"),
                args=[str(argument) for argument in item.get("args", ())],
                cwd=cwd,
                env=env,
                url=item.get("url"),
                headers=headers,
                allowed_tools=list(reads if item.get("confirmation_required") else reads + writes),
                blocked_tools=list(writes if item.get("confirmation_required") else ()),
                tool_prefix=item.get("tool_prefix", name),
                cache_tools=bool(item.get("cache_tools", True)),
                require_approval=False,
                startup_timeout_seconds=float(item.get("startup_timeout_seconds", 15)),
                call_timeout_seconds=float(item.get("call_timeout_seconds", 30)),
                client_session_timeout_seconds=float(item.get("client_session_timeout_seconds", 5)),
            )
        else:
            raise ValueError(f"{name}: unsupported MCP transport {transport!r}")

        references = tuple(
            str(reference["environment"])
            for reference in item.get("secret_references", ())
            if isinstance(reference, dict) and "environment" in reference
        )
        required_by = tuple(str(value) for value in item.get("required_by", ()))
        return MCPServerDefinition(
            name=name,
            transport=transport,
            read_tools=reads,
            write_tools=writes,
            confirmation_required=bool(item.get("confirmation_required", False)),
            validation_command=str(item.get("validation_command", "")),
            installation_status=str(item.get("installation_status", "optional")),
            adapter=str(adapter) if adapter is not None else None,
            secret_references=references,
            required_by=required_by,
            operational=operational,
        )

    @staticmethod
    def _resolve_environment(references: list[str] | tuple[str, ...]) -> dict[str, str]:
        return {name: os.environ[name] for name in references if name in os.environ}

    @staticmethod
    def _resolve_headers(references: dict[str, str]) -> dict[str, str]:
        return {
            header: os.environ[environment]
            for header, environment in references.items()
            if environment in os.environ
        }

    def assigned(self, names: list[str]) -> list[MCPServerDefinition]:
        unknown = set(names) - self.servers.keys()
        if unknown:
            raise ValueError(f"unknown MCP servers: {sorted(unknown)}")
        return [self.servers[name] for name in names]

    def tools(self, server: str, *, include_writes: bool = False) -> tuple[str, ...]:
        definition = self.servers[server]
        tools = list(definition.read_tools)
        if include_writes:
            if definition.confirmation_required:
                raise PermissionError(
                    "MCP write tools require a durable approval bound to the exact call; "
                    "the compatibility facade cannot grant authority"
                )
            tools.extend(definition.write_tools)
        result = tuple(tools)
        self._tool_cache[server] = result
        return result

    def permissions(self, names: list[str]) -> dict[str, dict[str, Any]]:
        return {
            item.name: {
                "read": item.read_tools,
                "write": item.write_tools,
                "approval_required": item.confirmation_required,
                "adapter": item.adapter,
            }
            for item in self.assigned(names)
        }

    async def connect(self) -> None:
        try:
            await self.manager.connect_all()
        except Exception as exc:
            self._connection_error = f"{type(exc).__name__}: {exc}"
            self._connected = False
            raise
        else:
            self._connection_error = None
            self._connected = True

    async def connect_assigned(self, server_name: str) -> tuple[list[Any], list[str]]:
        """Connect one local server in an isolated run-scoped manager."""
        definition = self.servers[server_name]
        if definition.operational is None:
            raise ValueError(f"{server_name!r} is host-provided and cannot connect locally")
        manager = MCPManager()
        manager.register(definition.operational)
        try:
            await manager.connect_all()
            tools = await manager.list_tools()
        except BaseException:
            try:
                await manager.cleanup()
            except BaseException:
                pass
            raise
        self._run_managers.append(manager)
        return manager.servers, [item.exposed_name for item in tools]

    def health(self) -> dict[str, str]:
        result: dict[str, str] = {}
        for name, item in self.servers.items():
            if item.operational is not None:
                if self._connected:
                    result[name] = "PASS"
                elif self._connection_error is not None:
                    result[name] = "DEGRADED"
                else:
                    result[name] = "SKIPPED" if "optional" in item.installation_status else "DEGRADED"
            elif item.installation_status in {"built-in", "host-provided"}:
                result[name] = "PASS"
            else:
                result[name] = "SKIPPED"
        return result

    async def close(self) -> None:
        errors: list[BaseException] = []
        for manager in reversed(self._run_managers):
            try:
                await manager.cleanup()
            except BaseException as exc:
                errors.append(exc)
        self._run_managers.clear()
        if self._connected:
            try:
                await self.manager.cleanup()
            except BaseException as exc:
                errors.append(exc)
        self._connected = False
        self._tool_cache.clear()
        if errors:
            raise BaseExceptionGroup("MCP cleanup failures", errors)
