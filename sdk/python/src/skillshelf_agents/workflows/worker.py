from __future__ import annotations

from .engine import DurableWorkflowEngine, WorkflowRunStatus


class WorkflowWorker:
    def __init__(self, engine: DurableWorkflowEngine) -> None:
        self.engine = engine

    def run_once(self) -> WorkflowRunStatus | None:
        return self.engine.work_once()

    def run_until_idle(self, *, maximum_runs: int = 100) -> list[WorkflowRunStatus]:
        completed: list[WorkflowRunStatus] = []
        for _ in range(maximum_runs):
            result = self.run_once()
            if result is None:
                break
            completed.append(result)
        return completed
