from __future__ import annotations

import hashlib
import hmac
import json
import sqlite3
import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from .definitions import WorkflowDefinition, WorkflowState, WorkflowStepDefinition
from .registry import WorkflowRegistry
from .retries import is_retryable, next_retry_at


def _json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _digest(value: Any) -> str:
    return hashlib.sha256(_json(value).encode()).hexdigest()


class WorkflowStepStatus(BaseModel):
    id: str
    attempt: int
    state: WorkflowState
    input_digest: str | None
    output_digest: str | None
    started_at: datetime | None
    completed_at: datetime | None
    next_retry_at: datetime | None
    error_code: str | None
    approval_id: str | None
    external_correlation_id: str | None


class WorkflowRunStatus(BaseModel):
    id: str
    workflow_id: str
    workflow_version: int
    state: WorkflowState
    input: dict[str, Any]
    output: dict[str, Any]
    idempotency_key: str
    created_at: datetime
    updated_at: datetime
    steps: list[WorkflowStepStatus]


class WaitForExternalEvent(RuntimeError):
    def __init__(self, correlation_id: str) -> None:
        super().__init__("workflow is waiting for an external event")
        if not correlation_id:
            raise ValueError("external correlation ID is required")
        self.correlation_id = correlation_id


class DurableWorkflowEngine:
    def __init__(
        self,
        path: Path | str,
        registry: WorkflowRegistry,
        handlers: dict[str, Callable[[dict[str, Any]], dict[str, Any]]],
        *,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.registry = registry
        self.handlers = handlers
        self.clock = clock
        self.connection = sqlite3.connect(self.path)
        self.connection.row_factory = sqlite3.Row
        self.connection.executescript(
            """
            PRAGMA foreign_keys=ON;
            CREATE TABLE IF NOT EXISTS durable_workflow_runs (
              id TEXT PRIMARY KEY,
              workflow_id TEXT NOT NULL,
              workflow_version INTEGER NOT NULL,
              state TEXT NOT NULL,
              input_json TEXT NOT NULL,
              output_json TEXT NOT NULL,
              idempotency_key TEXT NOT NULL,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL,
              UNIQUE(workflow_id, workflow_version, idempotency_key)
            );
            CREATE TABLE IF NOT EXISTS durable_workflow_steps (
              run_id TEXT NOT NULL,
              position INTEGER NOT NULL,
              step_id TEXT NOT NULL,
              attempt INTEGER NOT NULL DEFAULT 0,
              state TEXT NOT NULL,
              input_digest TEXT,
              output_digest TEXT,
              started_at TEXT,
              completed_at TEXT,
              next_retry_at TEXT,
              error_code TEXT,
              approval_id TEXT,
              external_correlation_id TEXT,
              PRIMARY KEY(run_id, step_id),
              FOREIGN KEY(run_id) REFERENCES durable_workflow_runs(id)
            );
            CREATE TABLE IF NOT EXISTS durable_workflow_queue (
              run_id TEXT PRIMARY KEY,
              available_at TEXT NOT NULL,
              leased_at TEXT,
              FOREIGN KEY(run_id) REFERENCES durable_workflow_runs(id)
            );
            CREATE TABLE IF NOT EXISTS durable_workflow_events (
              id INTEGER PRIMARY KEY,
              run_id TEXT NOT NULL,
              event_type TEXT NOT NULL,
              payload_json TEXT NOT NULL,
              created_at TEXT NOT NULL,
              FOREIGN KEY(run_id) REFERENCES durable_workflow_runs(id)
            );
            CREATE TABLE IF NOT EXISTS durable_workflow_dead_letters (
              run_id TEXT PRIMARY KEY,
              step_id TEXT NOT NULL,
              error_code TEXT NOT NULL,
              payload_json TEXT NOT NULL,
              created_at TEXT NOT NULL
            );
            """
        )

    def _event(self, run_id: str, event_type: str, payload: dict[str, Any]) -> None:
        self.connection.execute(
            "INSERT INTO durable_workflow_events(run_id,event_type,payload_json,created_at) VALUES(?,?,?,?)",
            (run_id, event_type, _json(payload), self.clock().isoformat()),
        )

    def _enqueue(self, run_id: str, available_at: datetime | None = None) -> None:
        self.connection.execute(
            """INSERT INTO durable_workflow_queue(run_id,available_at,leased_at) VALUES(?,?,NULL)
               ON CONFLICT(run_id) DO UPDATE SET available_at=excluded.available_at,leased_at=NULL""",
            (run_id, (available_at or self.clock()).isoformat()),
        )

    def start(
        self,
        workflow_id: str,
        workflow_input: dict[str, Any],
        *,
        idempotency_key: str,
        run_id: str | None = None,
    ) -> WorkflowRunStatus:
        definition = self.registry.inspect(workflow_id)
        existing = self.connection.execute(
            """SELECT id FROM durable_workflow_runs
               WHERE workflow_id=? AND workflow_version=? AND idempotency_key=?""",
            (workflow_id, definition.version, idempotency_key),
        ).fetchone()
        if existing:
            return self.status(str(existing["id"]))
        identifier = run_id or f"wf-{uuid.uuid4().hex}"
        at = self.clock()
        with self.connection:
            self.connection.execute(
                "INSERT INTO durable_workflow_runs VALUES(?,?,?,?,?,?,?,?,?)",
                (
                    identifier,
                    workflow_id,
                    definition.version,
                    WorkflowState.PENDING,
                    _json(workflow_input),
                    "{}",
                    idempotency_key,
                    at.isoformat(),
                    at.isoformat(),
                ),
            )
            for position, step in enumerate(definition.steps):
                self.connection.execute(
                    """INSERT INTO durable_workflow_steps
                       (run_id,position,step_id,attempt,state) VALUES(?,?,?,?,?)""",
                    (identifier, position, step.id, 0, WorkflowState.PENDING),
                )
            self._enqueue(identifier)
            self._event(identifier, "workflow.started", {"input_digest": _digest(workflow_input)})
        return self.status(identifier)

    def _definition(self, run: sqlite3.Row) -> WorkflowDefinition:
        definition = self.registry.inspect(str(run["workflow_id"]))
        if definition.version != int(run["workflow_version"]):
            raise RuntimeError("registered workflow version differs from persisted run")
        return definition

    def _step_definition(self, definition: WorkflowDefinition, step_id: str) -> WorkflowStepDefinition:
        return next(step for step in definition.steps if step.id == step_id)

    def _claim(self) -> str | None:
        now = self.clock().isoformat()
        row = self.connection.execute(
            """SELECT run_id FROM durable_workflow_queue
               WHERE available_at<=? AND leased_at IS NULL ORDER BY available_at,run_id LIMIT 1""",
            (now,),
        ).fetchone()
        if row is None:
            return None
        run_id = str(row["run_id"])
        changed = self.connection.execute(
            "UPDATE durable_workflow_queue SET leased_at=? WHERE run_id=? AND leased_at IS NULL",
            (now, run_id),
        ).rowcount
        self.connection.commit()
        return run_id if changed else None

    def work_once(self) -> WorkflowRunStatus | None:
        run_id = self._claim()
        if run_id is None:
            return None
        run = self.connection.execute("SELECT * FROM durable_workflow_runs WHERE id=?", (run_id,)).fetchone()
        assert run is not None
        definition = self._definition(run)
        output = json.loads(run["output_json"]) or json.loads(run["input_json"])
        with self.connection:
            self.connection.execute(
                "UPDATE durable_workflow_runs SET state=?,updated_at=? WHERE id=?",
                (WorkflowState.RUNNING, self.clock().isoformat(), run_id),
            )
        for step in definition.steps:
            row = self.connection.execute(
                "SELECT * FROM durable_workflow_steps WHERE run_id=? AND step_id=?",
                (run_id, step.id),
            ).fetchone()
            assert row is not None
            state = WorkflowState(row["state"])
            if state == WorkflowState.COMPLETED:
                continue
            if state == WorkflowState.WAITING_FOR_APPROVAL:
                self._release_queue(run_id)
                return self.status(run_id)
            if step.approval_policy and not row["approval_id"]:
                approval_id = f"approval-{_digest([run_id, step.id])[:24]}"
                with self.connection:
                    self.connection.execute(
                        """UPDATE durable_workflow_steps SET state=?,approval_id=?,
                           input_digest=? WHERE run_id=? AND step_id=?""",
                        (
                            WorkflowState.WAITING_FOR_APPROVAL,
                            approval_id,
                            _digest(output),
                            run_id,
                            step.id,
                        ),
                    )
                    self.connection.execute(
                        "UPDATE durable_workflow_runs SET state=?,updated_at=? WHERE id=?",
                        (WorkflowState.WAITING_FOR_APPROVAL, self.clock().isoformat(), run_id),
                    )
                    self._event(
                        run_id, "workflow.approval_required", {"step_id": step.id, "approval_id": approval_id}
                    )
                    self._release_queue(run_id)
                return self.status(run_id)
            attempt = int(row["attempt"]) + 1
            started = self.clock()
            with self.connection:
                self.connection.execute(
                    """UPDATE durable_workflow_steps SET attempt=?,state=?,input_digest=?,
                       started_at=?,next_retry_at=NULL,error_code=NULL WHERE run_id=? AND step_id=?""",
                    (attempt, WorkflowState.RUNNING, _digest(output), started.isoformat(), run_id, step.id),
                )
            try:
                handler = self.handlers[step.handler]
                step_output = handler(dict(output))
                if not isinstance(step_output, dict):
                    raise TypeError("workflow handler must return an object")
            except WaitForExternalEvent as waiting:
                with self.connection:
                    self.connection.execute(
                        """UPDATE durable_workflow_steps SET state=?,external_correlation_id=?,
                           error_code=NULL WHERE run_id=? AND step_id=?""",
                        (
                            WorkflowState.WAITING_FOR_EXTERNAL_EVENT,
                            waiting.correlation_id,
                            run_id,
                            step.id,
                        ),
                    )
                    self.connection.execute(
                        "UPDATE durable_workflow_runs SET state=?,updated_at=? WHERE id=?",
                        (
                            WorkflowState.WAITING_FOR_EXTERNAL_EVENT,
                            self.clock().isoformat(),
                            run_id,
                        ),
                    )
                    self._event(
                        run_id,
                        "workflow.external_event_required",
                        {"step_id": step.id, "correlation_id": waiting.correlation_id},
                    )
                    self._release_queue(run_id)
                return self.status(run_id)
            except Exception as error:
                return self._handle_failure(run_id, step, attempt, output, error)
            output = step_output
            completed = self.clock()
            with self.connection:
                self.connection.execute(
                    """UPDATE durable_workflow_steps SET state=?,output_digest=?,completed_at=?
                       WHERE run_id=? AND step_id=?""",
                    (WorkflowState.COMPLETED, _digest(output), completed.isoformat(), run_id, step.id),
                )
                self.connection.execute(
                    "UPDATE durable_workflow_runs SET output_json=?,updated_at=? WHERE id=?",
                    (_json(output), completed.isoformat(), run_id),
                )
                self._event(run_id, "workflow.step_completed", {"step_id": step.id, "attempt": attempt})
        with self.connection:
            self.connection.execute(
                "UPDATE durable_workflow_runs SET state=?,updated_at=? WHERE id=?",
                (WorkflowState.COMPLETED, self.clock().isoformat(), run_id),
            )
            self._event(run_id, "workflow.completed", {"output_digest": _digest(output)})
            self._release_queue(run_id)
        return self.status(run_id)

    def _handle_failure(
        self,
        run_id: str,
        step: WorkflowStepDefinition,
        attempt: int,
        payload: dict[str, Any],
        error: Exception,
    ) -> WorkflowRunStatus:
        error_code = type(error).__name__
        if attempt < step.retry_policy.maximum_attempts and is_retryable(step.retry_policy, error):
            retry_at = next_retry_at(step.retry_policy, attempt, self.clock())
            state = WorkflowState.RETRYING
            with self.connection:
                self.connection.execute(
                    """UPDATE durable_workflow_steps SET state=?,next_retry_at=?,error_code=?
                       WHERE run_id=? AND step_id=?""",
                    (state, retry_at.isoformat(), error_code, run_id, step.id),
                )
                self.connection.execute(
                    "UPDATE durable_workflow_runs SET state=?,updated_at=? WHERE id=?",
                    (state, self.clock().isoformat(), run_id),
                )
                self._event(run_id, "workflow.retry_scheduled", {"step_id": step.id, "attempt": attempt})
                self._release_queue(run_id)
            return self.status(run_id)
        with self.connection:
            self.connection.execute(
                "UPDATE durable_workflow_steps SET state=?,error_code=? WHERE run_id=? AND step_id=?",
                (WorkflowState.DEAD_LETTERED, error_code, run_id, step.id),
            )
            self.connection.execute(
                "UPDATE durable_workflow_runs SET state=?,updated_at=? WHERE id=?",
                (WorkflowState.DEAD_LETTERED, self.clock().isoformat(), run_id),
            )
            self.connection.execute(
                "INSERT OR REPLACE INTO durable_workflow_dead_letters VALUES(?,?,?,?,?)",
                (run_id, step.id, error_code, _json(payload), self.clock().isoformat()),
            )
            self._event(run_id, "workflow.dead_lettered", {"step_id": step.id, "error_code": error_code})
            self._release_queue(run_id)
        return self.status(run_id)

    def _release_queue(self, run_id: str) -> None:
        self.connection.execute("DELETE FROM durable_workflow_queue WHERE run_id=?", (run_id,))

    def schedule_due(self) -> int:
        now = self.clock()
        rows = self.connection.execute(
            """SELECT DISTINCT run_id FROM durable_workflow_steps
               WHERE state=? AND next_retry_at<=?""",
            (WorkflowState.RETRYING, now.isoformat()),
        ).fetchall()
        with self.connection:
            for row in rows:
                run_id = str(row["run_id"])
                self.connection.execute(
                    """UPDATE durable_workflow_steps SET state=?
                       WHERE run_id=? AND state=? AND next_retry_at<=?""",
                    (WorkflowState.PENDING, run_id, WorkflowState.RETRYING, now.isoformat()),
                )
                self.connection.execute(
                    "UPDATE durable_workflow_runs SET state=?,updated_at=? WHERE id=?",
                    (WorkflowState.PENDING, now.isoformat(), run_id),
                )
                self._enqueue(run_id, now)
        return len(rows)

    def approve(self, run_id: str, step_id: str, *, approval_id: str) -> WorkflowRunStatus:
        row = self.connection.execute(
            "SELECT approval_id,state FROM durable_workflow_steps WHERE run_id=? AND step_id=?",
            (run_id, step_id),
        ).fetchone()
        if row is None or row["approval_id"] != approval_id:
            raise PermissionError("approval does not match the exact workflow step")
        if WorkflowState(row["state"]) != WorkflowState.WAITING_FOR_APPROVAL:
            raise ValueError("workflow step is not waiting for approval")
        with self.connection:
            self.connection.execute(
                "UPDATE durable_workflow_steps SET state=? WHERE run_id=? AND step_id=?",
                (WorkflowState.PENDING, run_id, step_id),
            )
            self.connection.execute(
                "UPDATE durable_workflow_runs SET state=?,updated_at=? WHERE id=?",
                (WorkflowState.PENDING, self.clock().isoformat(), run_id),
            )
            self._enqueue(run_id)
            self._event(run_id, "workflow.approved", {"step_id": step_id, "approval_id": approval_id})
        return self.status(run_id)

    def cancel(self, run_id: str) -> WorkflowRunStatus:
        current = self.status(run_id)
        if current.state in {WorkflowState.COMPLETED, WorkflowState.DEAD_LETTERED}:
            raise ValueError("terminal workflow cannot be cancelled")
        with self.connection:
            self.connection.execute(
                "UPDATE durable_workflow_runs SET state=?,updated_at=? WHERE id=?",
                (WorkflowState.CANCELLED, self.clock().isoformat(), run_id),
            )
            self._release_queue(run_id)
            self._event(run_id, "workflow.cancelled", {})
        return self.status(run_id)

    def retry(self, run_id: str, step_id: str) -> WorkflowRunStatus:
        row = self.connection.execute(
            "SELECT state FROM durable_workflow_steps WHERE run_id=? AND step_id=?", (run_id, step_id)
        ).fetchone()
        if row is None or WorkflowState(row["state"]) not in {
            WorkflowState.DEAD_LETTERED,
            WorkflowState.FAILED,
            WorkflowState.RETRYING,
        }:
            raise ValueError("step is not retryable")
        with self.connection:
            self.connection.execute(
                """UPDATE durable_workflow_steps SET state=?,next_retry_at=NULL,error_code=NULL
                   WHERE run_id=? AND step_id=?""",
                (WorkflowState.PENDING, run_id, step_id),
            )
            self.connection.execute(
                "UPDATE durable_workflow_runs SET state=?,updated_at=? WHERE id=?",
                (WorkflowState.PENDING, self.clock().isoformat(), run_id),
            )
            self.connection.execute("DELETE FROM durable_workflow_dead_letters WHERE run_id=?", (run_id,))
            self._enqueue(run_id)
        return self.status(run_id)

    def resume(self, run_id: str) -> WorkflowRunStatus:
        current = self.status(run_id)
        if current.state not in {
            WorkflowState.PENDING,
            WorkflowState.RETRYING,
            WorkflowState.WAITING_FOR_EXTERNAL_EVENT,
            WorkflowState.PARTIALLY_COMPLETED,
        }:
            raise ValueError("workflow is not resumable")
        with self.connection:
            self._enqueue(run_id)
        return self.status(run_id)

    def signal_external_event(
        self,
        run_id: str,
        step_id: str,
        *,
        correlation_id: str,
        payload: dict[str, Any],
    ) -> WorkflowRunStatus:
        row = self.connection.execute(
            """SELECT state,external_correlation_id FROM durable_workflow_steps
               WHERE run_id=? AND step_id=?""",
            (run_id, step_id),
        ).fetchone()
        if row is None or WorkflowState(row["state"]) != WorkflowState.WAITING_FOR_EXTERNAL_EVENT:
            raise ValueError("workflow step is not waiting for an external event")
        if not hmac_compare(str(row["external_correlation_id"]), correlation_id):
            raise PermissionError("external correlation ID does not match")
        run = self.status(run_id)
        merged = {**(run.output or run.input), "external_event": payload}
        with self.connection:
            self.connection.execute(
                """UPDATE durable_workflow_steps SET state=?,output_digest=?,completed_at=?
                   WHERE run_id=? AND step_id=?""",
                (
                    WorkflowState.COMPLETED,
                    _digest(merged),
                    self.clock().isoformat(),
                    run_id,
                    step_id,
                ),
            )
            self.connection.execute(
                "UPDATE durable_workflow_runs SET state=?,output_json=?,updated_at=? WHERE id=?",
                (WorkflowState.PENDING, _json(merged), self.clock().isoformat(), run_id),
            )
            self._enqueue(run_id)
            self._event(
                run_id,
                "workflow.external_event_received",
                {"step_id": step_id, "correlation_id": correlation_id, "payload_digest": _digest(payload)},
            )
        return self.status(run_id)

    def dead_letters(self) -> list[dict[str, Any]]:
        return [
            {
                "run_id": row["run_id"],
                "step_id": row["step_id"],
                "error_code": row["error_code"],
                "payload": json.loads(row["payload_json"]),
                "created_at": row["created_at"],
            }
            for row in self.connection.execute(
                "SELECT * FROM durable_workflow_dead_letters ORDER BY created_at,run_id"
            )
        ]

    def status(self, run_id: str) -> WorkflowRunStatus:
        run = self.connection.execute("SELECT * FROM durable_workflow_runs WHERE id=?", (run_id,)).fetchone()
        if run is None:
            raise KeyError(run_id)
        steps = [
            WorkflowStepStatus(
                id=row["step_id"],
                attempt=row["attempt"],
                state=row["state"],
                input_digest=row["input_digest"],
                output_digest=row["output_digest"],
                started_at=datetime.fromisoformat(row["started_at"]) if row["started_at"] else None,
                completed_at=datetime.fromisoformat(row["completed_at"]) if row["completed_at"] else None,
                next_retry_at=datetime.fromisoformat(row["next_retry_at"]) if row["next_retry_at"] else None,
                error_code=row["error_code"],
                approval_id=row["approval_id"],
                external_correlation_id=row["external_correlation_id"],
            )
            for row in self.connection.execute(
                "SELECT * FROM durable_workflow_steps WHERE run_id=? ORDER BY position", (run_id,)
            )
        ]
        return WorkflowRunStatus(
            id=run["id"],
            workflow_id=run["workflow_id"],
            workflow_version=run["workflow_version"],
            state=run["state"],
            input=json.loads(run["input_json"]),
            output=json.loads(run["output_json"]),
            idempotency_key=run["idempotency_key"],
            created_at=datetime.fromisoformat(run["created_at"]),
            updated_at=datetime.fromisoformat(run["updated_at"]),
            steps=steps,
        )

    def list(self) -> list[WorkflowRunStatus]:
        return [
            self.status(str(row["id"]))
            for row in self.connection.execute(
                "SELECT id FROM durable_workflow_runs ORDER BY created_at DESC,id"
            )
        ]

    def close(self) -> None:
        self.connection.close()


def hmac_compare(left: str, right: str) -> bool:
    return hmac.compare_digest(left, right)
