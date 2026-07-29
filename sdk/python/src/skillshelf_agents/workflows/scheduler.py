from __future__ import annotations

from .engine import DurableWorkflowEngine


class WorkflowScheduler:
    def __init__(self, engine: DurableWorkflowEngine) -> None:
        self.engine = engine

    def run_once(self) -> int:
        return self.engine.schedule_due()
