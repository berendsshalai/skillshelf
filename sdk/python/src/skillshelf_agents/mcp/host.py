from __future__ import annotations

from collections.abc import Callable

from agents import FunctionTool

from ..registry import AgentDefinition
from ..runtime.context import RuntimeContext


class StaticHostToolProvider:
    """Explicit host-installed adapter; YAML alone never makes it available."""

    def __init__(
        self,
        provider_id: str,
        tool_builder: Callable[[AgentDefinition, RuntimeContext], list[FunctionTool]],
        *,
        available: Callable[[], bool] | None = None,
    ) -> None:
        self.provider_id = provider_id
        self._tool_builder = tool_builder
        self._available = available or (lambda: True)

    def is_available(self) -> bool:
        return bool(self._available())

    def tools_for(
        self,
        agent_definition: AgentDefinition,
        runtime_context: RuntimeContext,
    ) -> list[FunctionTool]:
        return self._tool_builder(agent_definition, runtime_context)
