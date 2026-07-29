from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from collections.abc import Sequence
from typing import TYPE_CHECKING, Any, Protocol

from agents import FunctionTool
from pydantic import BaseModel

from ..registry import AgentDefinition
from ..runtime.capabilities import CapabilityProviderType
from ..runtime.context import RuntimeContext

if TYPE_CHECKING:
    from ..mcp_runtime import MCPRuntime


class MCPDegradedReason(BaseModel):
    server_name: str
    reason: str
    required: bool
    exception_type: str | None = None


@dataclass
class MCPAssignment:
    connected_servers: list[Any] = field(default_factory=list)
    host_tools: list[FunctionTool] = field(default_factory=list)
    degraded: list[MCPDegradedReason] = field(default_factory=list)
    tool_names: list[str] = field(default_factory=list)
    provider_tools: dict[str, list[str]] = field(default_factory=dict)
    provider_types: dict[str, CapabilityProviderType] = field(default_factory=dict)
    tool_list_digests: dict[str, str] = field(default_factory=dict)


class HostToolProvider(Protocol):
    provider_id: str

    def is_available(self) -> bool: ...

    def tools_for(
        self,
        agent_definition: AgentDefinition,
        runtime_context: RuntimeContext,
    ) -> list[FunctionTool]: ...


class MCPRequiredServerUnavailable(RuntimeError):
    pass


class MCPAssignmentResolver:
    def __init__(
        self,
        runtime: MCPRuntime,
        host_providers: Sequence[HostToolProvider] | None = None,
    ) -> None:
        self.runtime = runtime
        self.host_providers = {provider.provider_id: provider for provider in (host_providers or [])}

    async def resolve_for_agent(
        self,
        agent_definition: AgentDefinition,
        runtime_context: RuntimeContext,
    ) -> MCPAssignment:
        assignment = MCPAssignment()
        for definition in self.runtime.assigned(agent_definition.allowed_mcp):
            required = definition.required_for(agent_definition.id)
            if definition.adapter == "host-provided":
                provider = self.host_providers.get(definition.name)
                if provider is None or not provider.is_available():
                    self._degrade_or_raise(
                        assignment,
                        server_name=definition.name,
                        required=required,
                        reason="host provider is not installed or available",
                    )
                    continue
                tools = provider.tools_for(agent_definition, runtime_context)
                names = [tool.name for tool in tools]
                if not names:
                    self._degrade_or_raise(
                        assignment,
                        server_name=definition.name,
                        required=required,
                        reason="host provider returned no declared tools",
                    )
                    continue
                assignment.host_tools.extend(tools)
                assignment.tool_names.extend(names)
                assignment.provider_tools[definition.name] = names
                assignment.provider_types[definition.name] = CapabilityProviderType.HOST
                assignment.tool_list_digests[definition.name] = _tool_digest(names)
                continue
            try:
                connected, names = await self.runtime.connect_assigned(definition.name)
            except BaseException as exc:
                self._degrade_or_raise(
                    assignment,
                    server_name=definition.name,
                    required=required,
                    reason=str(exc) or type(exc).__name__,
                    exception_type=type(exc).__name__,
                )
                continue
            assignment.connected_servers.extend(connected)
            assignment.tool_names.extend(names)
            assignment.provider_tools[definition.name] = names
            assignment.provider_types[definition.name] = CapabilityProviderType.MCP
            assignment.tool_list_digests[definition.name] = _tool_digest(names)
        return assignment

    @staticmethod
    def _degrade_or_raise(
        assignment: MCPAssignment,
        *,
        server_name: str,
        required: bool,
        reason: str,
        exception_type: str | None = None,
    ) -> None:
        item = MCPDegradedReason(
            server_name=server_name,
            reason=reason,
            required=required,
            exception_type=exception_type,
        )
        assignment.degraded.append(item)
        if required:
            raise MCPRequiredServerUnavailable(
                f"required MCP/host provider {server_name!r} is unavailable: {reason}"
            )


def _tool_digest(names: list[str]) -> str:
    payload = json.dumps(sorted(names), separators=(",", ":")).encode()
    return hashlib.sha256(payload).hexdigest()
