from __future__ import annotations

from .engine import DurableWorkflowEngine, WorkflowRunStatus


class WorkflowApprovals:
    def __init__(self, engine: DurableWorkflowEngine) -> None:
        self.engine = engine

    def approve(self, run_id: str, step_id: str, approval_id: str) -> WorkflowRunStatus:
        return self.engine.approve(run_id, step_id, approval_id=approval_id)
