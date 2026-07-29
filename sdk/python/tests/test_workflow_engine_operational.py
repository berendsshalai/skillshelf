from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from skillshelf_agents.workflows import (
    DurableWorkflowEngine,
    RetryPolicy,
    WorkflowDefinition,
    WorkflowRegistry,
    WorkflowState,
    WorkflowStepDefinition,
)
from skillshelf_agents.workflows.worker import WorkflowWorker


def _registry() -> WorkflowRegistry:
    registry = WorkflowRegistry()
    registry.register(
        WorkflowDefinition(
            id="restart-safe",
            version=1,
            input_schema="test",
            steps=[
                WorkflowStepDefinition(
                    id="perform",
                    handler="perform",
                    retry_policy=RetryPolicy(maximum_attempts=2, base_delay_seconds=0),
                )
            ],
        )
    )
    return registry


def test_worker_restart_resumes_due_retry_without_replaying_completed_attempt(tmp_path: Path) -> None:
    path = tmp_path / "durable.sqlite"
    attempts = 0

    def perform(value: dict[str, object]) -> dict[str, object]:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise TimeoutError("temporary")
        return {**value, "complete": True}

    at = datetime(2026, 7, 28, tzinfo=UTC)
    first_process = DurableWorkflowEngine(path, _registry(), {"perform": perform}, clock=lambda: at)
    run = first_process.start("restart-safe", {"id": "A"}, idempotency_key="A")
    WorkflowWorker(first_process).run_once()
    assert first_process.status(run.id).state == WorkflowState.RETRYING
    first_process.close()

    second_process = DurableWorkflowEngine(path, _registry(), {"perform": perform}, clock=lambda: at)
    assert second_process.schedule_due() == 1
    WorkflowWorker(second_process).run_once()
    completed = second_process.status(run.id)
    assert completed.state == WorkflowState.COMPLETED
    assert completed.steps[0].attempt == 2
    assert second_process.start("restart-safe", {"id": "A"}, idempotency_key="A").id == run.id
    second_process.close()


def test_non_retryable_failure_is_persisted_to_dead_letter(tmp_path: Path) -> None:
    def fail(_value: dict[str, object]) -> dict[str, object]:
        raise ValueError("permanent")

    at = datetime(2026, 7, 28, tzinfo=UTC)
    engine = DurableWorkflowEngine(
        tmp_path / "dead-letter.sqlite", _registry(), {"perform": fail}, clock=lambda: at
    )
    run = engine.start("restart-safe", {"id": "B"}, idempotency_key="B")
    WorkflowWorker(engine).run_once()
    assert engine.status(run.id).state == WorkflowState.DEAD_LETTERED
    assert engine.dead_letters() == [
        {
            "run_id": run.id,
            "step_id": "perform",
            "error_code": "ValueError",
            "payload": {"id": "B"},
            "created_at": at.isoformat(),
        }
    ]
    engine.close()
