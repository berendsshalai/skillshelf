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


class ApprovalRecord(BaseModel):
    approval_id: str
    run_id: str
    tool_name: str
    arguments_digest: str
    operation: str
    authorised_root: str
    expires_at: datetime
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
                    tool_name TEXT NOT NULL,
                    arguments_digest TEXT NOT NULL,
                    operation TEXT NOT NULL,
                    authorised_root TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    approving_user TEXT NOT NULL,
                    status TEXT NOT NULL CHECK(status IN ('pending','approved','rejected')),
                    created_at TEXT NOT NULL,
                    decided_at TEXT
                )
                """
            )

    def request(
        self,
        *,
        context: RuntimeContext,
        tool_name: str,
        arguments: dict[str, Any],
        operation: str,
        approving_user: str,
        ttl_seconds: int,
    ) -> ApprovalRecord:
        if ttl_seconds < 1:
            raise ValueError("approval expiry must be in the future")
        record = ApprovalRecord(
            approval_id=f"approval-{uuid.uuid4().hex}",
            run_id=context.run_id,
            tool_name=tool_name,
            arguments_digest=canonical_arguments_digest(arguments),
            operation=operation,
            authorised_root=str(context.repository_root),
            expires_at=datetime.now(UTC) + timedelta(seconds=ttl_seconds),
            approving_user=approving_user,
            status="pending",
        )
        with sqlite3.connect(self.database) as connection:
            connection.execute(
                """
                INSERT INTO runtime_approvals
                (approval_id,run_id,tool_name,arguments_digest,operation,authorised_root,
                 expires_at,approving_user,status,created_at)
                VALUES (?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    record.approval_id,
                    record.run_id,
                    record.tool_name,
                    record.arguments_digest,
                    record.operation,
                    record.authorised_root,
                    record.expires_at.isoformat(),
                    record.approving_user,
                    record.status,
                    datetime.now(UTC).isoformat(),
                ),
            )
        return record

    def _record(self, approval_id: str) -> ApprovalRecord:
        with sqlite3.connect(self.database) as connection:
            row = connection.execute(
                """
                SELECT approval_id,run_id,tool_name,arguments_digest,operation,authorised_root,
                       expires_at,approving_user,status
                FROM runtime_approvals WHERE approval_id=?
                """,
                (approval_id,),
            ).fetchone()
        if row is None:
            raise KeyError(approval_id)
        return ApprovalRecord.model_validate(dict(zip(ApprovalRecord.model_fields, row, strict=True)))

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
            identifiers = [
                str(row[0]) for row in connection.execute(query, arguments).fetchall()
            ]
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
