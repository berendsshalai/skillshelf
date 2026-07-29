from __future__ import annotations

from .engine import DurableWorkflowEngine, WorkflowRunStatus


class WorkflowExecutor:
    def __init__(self, engine: DurableWorkflowEngine) -> None:
        self.engine = engine

    def execute_once(self) -> WorkflowRunStatus | None:
        return self.engine.work_once()
