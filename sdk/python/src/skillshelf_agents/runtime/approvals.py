from __future__ import annotations

import hashlib
import json
import sqlite3
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel

from .context import RuntimeContext


def canonical_arguments_digest(arguments: dict[str, Any]) -> str:
    payload = json.dumps(arguments, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class PendingToolApproval(BaseModel):
    approval_id: str
    run_id: str
    session_id: str
    agent_id: str
    tool_name: str
    tool_call_id: str
    canonical_arguments: dict[str, Any]
    arguments_digest: str
    operation: str
    authorised_root: str
    created_at: datetime
    expires_at: datetime
    sdk_state_path: str


class ApprovalRecord(PendingToolApproval):
    approving_user: str
    status: Literal["pending", "approved", "rejected"]


class ApprovalStore:
    """Durable grants bound to run, tool, canonical arguments, root, user, and expiry."""

    def __init__(self, database: Path) -> None:
        self.database = database
        database.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(database) as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS runtime_approvals (
                    approval_id TEXT PRIMARY KEY,
                    run_id TEXT NOT NULL,
                    session_id TEXT NOT NULL,
                    agent_id TEXT NOT NULL,
                    tool_name TEXT NOT NULL,
                    tool_call_id TEXT NOT NULL,
                    canonical_arguments TEXT NOT NULL,
                    arguments_digest TEXT NOT NULL,
                    operation TEXT NOT NULL,
                    authorised_root TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    approving_user TEXT NOT NULL,
                    status TEXT NOT NULL CHECK(status IN ('pending','approved','rejected')),
                    created_at TEXT NOT NULL,
                    sdk_state_path TEXT NOT NULL,
                    decided_at TEXT
                )
                """
            )
            existing = {str(row[1]) for row in connection.execute("PRAGMA table_info(runtime_approvals)")}
            migrations = {
                "session_id": "TEXT NOT NULL DEFAULT ''",
                "agent_id": "TEXT NOT NULL DEFAULT ''",
                "tool_call_id": "TEXT NOT NULL DEFAULT ''",
                "canonical_arguments": "TEXT NOT NULL DEFAULT '{}'",
                "sdk_state_path": "TEXT NOT NULL DEFAULT ''",
            }
            for name, declaration in migrations.items():
                if name not in existing:
                    connection.execute(f"ALTER TABLE runtime_approvals ADD COLUMN {name} {declaration}")

    def request(
        self,
        *,
        context: RuntimeContext,
        tool_name: str,
        arguments: dict[str, Any],
        operation: str,
        approving_user: str,
        ttl_seconds: int,
        agent_id: str = "unknown-agent",
        tool_call_id: str | None = None,
        sdk_state_path: str = "",
    ) -> ApprovalRecord:
        if ttl_seconds < 1:
            raise ValueError("approval expiry must be in the future")
        created_at = datetime.now(UTC)
        canonical = json.loads(json.dumps(arguments, sort_keys=True, separators=(",", ":"), default=str))
        record = ApprovalRecord(
            approval_id=f"approval-{uuid.uuid4().hex}",
            run_id=context.run_id,
            session_id=context.session_id,
            agent_id=agent_id,
            tool_name=tool_name,
            tool_call_id=tool_call_id or f"call-{uuid.uuid4().hex}",
            canonical_arguments=canonical,
            arguments_digest=canonical_arguments_digest(arguments),
            operation=operation,
            authorised_root=str(context.repository_root),
            created_at=created_at,
            expires_at=created_at + timedelta(seconds=ttl_seconds),
            sdk_state_path=sdk_state_path,
            approving_user=approving_user,
            status="pending",
        )
        with sqlite3.connect(self.database) as connection:
            connection.execute(
                """
                INSERT INTO runtime_approvals
                (approval_id,run_id,session_id,agent_id,tool_name,tool_call_id,
                 canonical_arguments,arguments_digest,operation,authorised_root,
                 expires_at,approving_user,status,created_at,sdk_state_path)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    record.approval_id,
                    record.run_id,
                    record.session_id,
                    record.agent_id,
                    record.tool_name,
                    record.tool_call_id,
                    json.dumps(record.canonical_arguments, sort_keys=True, separators=(",", ":")),
                    record.arguments_digest,
                    record.operation,
                    record.authorised_root,
                    record.expires_at.isoformat(),
                    record.approving_user,
                    record.status,
                    record.created_at.isoformat(),
                    record.sdk_state_path,
                ),
            )
        return record

    def _record(self, approval_id: str) -> ApprovalRecord:
        with sqlite3.connect(self.database) as connection:
            row = connection.execute(
                """
                SELECT approval_id,run_id,session_id,agent_id,tool_name,tool_call_id,
                       canonical_arguments,arguments_digest,operation,authorised_root,
                       created_at,expires_at,sdk_state_path,approving_user,status
                FROM runtime_approvals WHERE approval_id=?
                """,
                (approval_id,),
            ).fetchone()
        if row is None:
            raise KeyError(approval_id)
        values = dict(zip(ApprovalRecord.model_fields, row, strict=True))
        values["canonical_arguments"] = json.loads(values["canonical_arguments"])
        return ApprovalRecord.model_validate(values)

    def inspect(self, approval_id: str) -> ApprovalRecord:
        return self._record(approval_id)

    def list(self, *, status: str | None = None) -> list[ApprovalRecord]:
        query = "SELECT approval_id FROM runtime_approvals"
        arguments: tuple[object, ...] = ()
        if status is not None:
            query += " WHERE status=?"
            arguments = (status,)
        query += " ORDER BY created_at"
        with sqlite3.connect(self.database) as connection:
            identifiers = [str(row[0]) for row in connection.execute(query, arguments).fetchall()]
        return [self._record(identifier) for identifier in identifiers]

    def approve(self, approval_id: str, *, approving_user: str) -> None:
        record = self._record(approval_id)
        if record.approving_user != approving_user:
            raise PermissionError("approval user does not match the bound user")
        self._decide(approval_id, "approved")

    def reject(self, approval_id: str, *, approving_user: str) -> None:
        record = self._record(approval_id)
        if record.approving_user != approving_user:
            raise PermissionError("approval user does not match the bound user")
        self._decide(approval_id, "rejected")

    def _decide(self, approval_id: str, status: Literal["approved", "rejected"]) -> None:
        with sqlite3.connect(self.database) as connection:
            cursor = connection.execute(
                """
                UPDATE runtime_approvals SET status=?, decided_at=?
                WHERE approval_id=? AND status='pending'
                """,
                (status, datetime.now(UTC).isoformat(), approval_id),
            )
            if cursor.rowcount != 1:
                raise ValueError("approval is no longer pending")

    def is_granted(self, approval_id: str) -> bool:
        record = self._record(approval_id)
        return record.status == "approved" and record.expires_at > datetime.now(UTC)

    def is_granted_for(
        self,
        approval_id: str,
        *,
        context: RuntimeContext,
        tool_name: str,
        arguments: dict[str, Any],
        operation: str,
    ) -> bool:
        record = self._record(approval_id)
        return bool(
            record.status == "approved"
            and record.expires_at > datetime.now(UTC)
            and record.run_id == context.run_id
            and record.tool_name == tool_name
            and record.arguments_digest == canonical_arguments_digest(arguments)
            and record.operation == operation
            and Path(record.authorised_root).resolve() == context.repository_root
        )

    def validate_resume(
        self,
        approval_id: str,
        *,
        context: RuntimeContext,
        tool_name: str,
        arguments: dict[str, Any],
        operation: str,
    ) -> ApprovalRecord:
        record = self._record(approval_id)
        if record.status != "approved":
            raise PermissionError(f"approval status is {record.status}")
        if record.expires_at <= datetime.now(UTC):
            raise PermissionError("approval has expired")
        if not self.is_granted_for(
            approval_id,
            context=context,
            tool_name=tool_name,
            arguments=arguments,
            operation=operation,
        ):
            if record.arguments_digest != canonical_arguments_digest(arguments):
                self._invalidate_approved(approval_id)
                raise PermissionError("tool arguments changed; a new approval is required")
            raise PermissionError("approval does not match the run, tool, operation, or repository")
        return record

    def _invalidate_approved(self, approval_id: str) -> None:
        with sqlite3.connect(self.database) as connection:
            connection.execute(
                """
                UPDATE runtime_approvals SET status='rejected', decided_at=?
                WHERE approval_id=? AND status='approved'
                """,
                (datetime.now(UTC).isoformat(), approval_id),
            )


class RunCheckpoint(BaseModel):
    run_id: str
    status: Literal["WAITING_FOR_APPROVAL", "RUNNING", "CANCELLED"]
    approval_id: str
    state_path: str
    state_digest: str
    updated_at: datetime


class RunCheckpointStore:
    """Durably stores only JSON-serializable SDK interruption state."""

    def __init__(self, directory: Path) -> None:
        self.directory = directory.resolve()
        self.directory.mkdir(parents=True, exist_ok=True)

    def persist_waiting(
        self,
        *,
        run_id: str,
        approval_id: str,
        state: dict[str, Any],
    ) -> RunCheckpoint:
        payload = json.dumps(state, sort_keys=True, separators=(",", ":"), default=str)
        path = self.directory / f"{run_id}.sdk-state.json"
        temporary = path.with_suffix(".tmp")
        temporary.write_text(payload, encoding="utf-8")
        temporary.replace(path)
        checkpoint = RunCheckpoint(
            run_id=run_id,
            status="WAITING_FOR_APPROVAL",
            approval_id=approval_id,
            state_path=str(path),
            state_digest=hashlib.sha256(payload.encode()).hexdigest(),
            updated_at=datetime.now(UTC),
        )
        self._write_checkpoint(checkpoint)
        return checkpoint

    def inspect(self, run_id: str) -> RunCheckpoint:
        path = self.directory / f"{run_id}.checkpoint.json"
        if not path.is_file():
            raise KeyError(run_id)
        return RunCheckpoint.model_validate_json(path.read_text(encoding="utf-8"))

    def load_state(self, run_id: str) -> dict[str, Any]:
        checkpoint = self.inspect(run_id)
        path = Path(checkpoint.state_path)
        content = path.read_bytes()
        if hashlib.sha256(content).hexdigest() != checkpoint.state_digest:
            raise ValueError("persisted SDK state digest does not match")
        return json.loads(content)

    def mark_running(self, run_id: str) -> RunCheckpoint:
        return self._transition(run_id, "RUNNING")

    def cancel(self, run_id: str) -> RunCheckpoint:
        return self._transition(run_id, "CANCELLED")

    def _transition(self, run_id: str, status: Literal["RUNNING", "CANCELLED"]) -> RunCheckpoint:
        current = self.inspect(run_id)
        if current.status != "WAITING_FOR_APPROVAL":
            raise ValueError(f"run cannot transition from {current.status}")
        updated = current.model_copy(update={"status": status, "updated_at": datetime.now(UTC)})
        self._write_checkpoint(updated)
        return updated

    def _write_checkpoint(self, checkpoint: RunCheckpoint) -> None:
        path = self.directory / f"{checkpoint.run_id}.checkpoint.json"
        temporary = path.with_suffix(".tmp")
        temporary.write_text(checkpoint.model_dump_json(), encoding="utf-8")
        temporary.replace(path)
