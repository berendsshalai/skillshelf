from __future__ import annotations

from typing import Any

from skillshelf_agents.runtime.approvals import ApprovalStore
from skillshelf_agents.runtime.context import RuntimeContext


class MCPApprovalGate:
    def __init__(self, store: ApprovalStore, *, context: RuntimeContext) -> None:
        self.store = store
        self.context = context

    def is_approved(
        self,
        approval_id: str,
        server_name: str,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> bool:
        return self.store.is_granted_for(
            approval_id,
            context=self.context,
            tool_name=f"mcp:{server_name}:{tool_name}",
            operation="call",
            arguments=arguments,
        )
