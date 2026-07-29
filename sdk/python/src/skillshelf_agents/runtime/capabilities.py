from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class CapabilityProviderType(StrEnum):
    FUNCTION_TOOL = "function_tool"
    MCP = "mcp"
    HOST = "host"
    DEGRADED = "degraded"


class CapabilityResolution(BaseModel):
    capability: str
    provider_type: CapabilityProviderType
    provider_name: str
    operational: bool
    tools: list[str] = Field(default_factory=list)
    reason: str | None = None
    required: bool = True


class CapabilityResolutionReport(BaseModel):
    agent_id: str
    resolutions: list[CapabilityResolution]

    @property
    def unresolved_required(self) -> list[CapabilityResolution]:
        return [item for item in self.resolutions if item.required and not item.operational]


class AgentCapabilityUnavailable(RuntimeError):
    def __init__(
        self,
        *,
        agent_id: str,
        capability: str,
        expected_providers: list[str],
        available_fallbacks: list[str],
    ) -> None:
        self.agent_id = agent_id
        self.capability = capability
        self.expected_providers = expected_providers
        self.available_fallbacks = available_fallbacks
        providers = ", ".join(expected_providers) or "none declared"
        fallbacks = ", ".join(available_fallbacks) or "none"
        super().__init__(
            f"Agent {agent_id!r} requires capability {capability!r}; expected provider(s): "
            f"{providers}; available fallbacks: {fallbacks}. Run `skillshelf doctor --deep`."
        )


class CapabilityResolver:
    """Resolve every declared capability without silently reducing the tool surface."""

    def __init__(self, function_tools: Any) -> None:
        self.function_tools = function_tools

    def resolve(
        self,
        agent_definition: Any,
        *,
        mcp_assignment: Any | None = None,
    ) -> CapabilityResolutionReport:
        provider_tools = dict(getattr(mcp_assignment, "provider_tools", {}))
        provider_types = dict(getattr(mcp_assignment, "provider_types", {}))
        degraded = {item.server_name: item.reason for item in getattr(mcp_assignment, "degraded", [])}
        resolutions: list[CapabilityResolution] = []
        for policy in agent_definition.capability_policies:
            capability = policy.id
            if self.function_tools.supports(capability):
                tools = [tool.name for tool in self.function_tools.build([capability])]
                resolutions.append(
                    CapabilityResolution(
                        capability=capability,
                        provider_type=CapabilityProviderType.FUNCTION_TOOL,
                        provider_name=capability,
                        operational=True,
                        tools=tools,
                        required=policy.required,
                    )
                )
                continue
            selected = next(
                (
                    provider
                    for provider in policy.providers
                    if provider in provider_tools and provider_tools[provider]
                ),
                None,
            )
            if selected is not None:
                resolutions.append(
                    CapabilityResolution(
                        capability=capability,
                        provider_type=provider_types.get(selected, CapabilityProviderType.MCP),
                        provider_name=selected,
                        operational=True,
                        tools=provider_tools[selected],
                        required=policy.required,
                    )
                )
                continue
            reasons = [
                f"{provider}: {degraded[provider]}" for provider in policy.providers if provider in degraded
            ]
            resolutions.append(
                CapabilityResolution(
                    capability=capability,
                    provider_type=CapabilityProviderType.DEGRADED,
                    provider_name=policy.providers[0] if policy.providers else capability,
                    operational=False,
                    required=policy.required,
                    reason="; ".join(reasons) or "no operational provider was resolved",
                )
            )
        report = CapabilityResolutionReport(agent_id=agent_definition.id, resolutions=resolutions)
        if report.unresolved_required:
            first = report.unresolved_required[0]
            policy = agent_definition.capability_policy_for(first.capability)
            raise AgentCapabilityUnavailable(
                agent_id=agent_definition.id,
                capability=first.capability,
                expected_providers=policy.providers,
                available_fallbacks=[item.provider_name for item in report.resolutions if item.operational],
            )
        return report
