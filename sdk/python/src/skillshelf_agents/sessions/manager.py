from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from agents import SQLiteSession

from .privacy import redact


SESSION_SCHEMA = """
CREATE TABLE IF NOT EXISTS skillshelf_session_metadata (
    session_id TEXT PRIMARY KEY,
    display_name TEXT NOT NULL,
    repository_identity TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS skillshelf_pending_approvals (
    approval_id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    FOREIGN KEY(session_id) REFERENCES skillshelf_session_metadata(session_id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS skillshelf_replay_checkpoints (
    checkpoint_id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    FOREIGN KEY(session_id) REFERENCES skillshelf_session_metadata(session_id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS skillshelf_session_artifacts (
    artifact_id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    retained INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY(session_id) REFERENCES skillshelf_session_metadata(session_id) ON DELETE CASCADE
);
"""


class UnifiedSessionManager:
    def __init__(self, database: Path) -> None:
        self.database = database.expanduser().resolve()
        self.database.parent.mkdir(parents=True, exist_ok=True)
        bootstrap = SQLiteSession("__bootstrap__", self.database)
        bootstrap.close()
        with self._connect() as connection:
            connection.executescript(SESSION_SCHEMA)

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        return connection

    def create(self, display_name: str, *, repository_identity: str) -> str:
        safe_name = display_name.strip()
        if not safe_name:
            raise ValueError("session display name cannot be empty")
        session_id = f"{repository_identity}:{safe_name}"
        self.create_with_id(session_id, repository_identity=repository_identity, display_name=safe_name)
        return session_id

    def create_with_id(
        self,
        session_id: str,
        *,
        repository_identity: str,
        display_name: str | None = None,
    ) -> None:
        now = datetime.now(UTC).isoformat()
        with self._connect() as connection:
            connection.execute(
                """
                INSERT OR IGNORE INTO skillshelf_session_metadata
                (session_id,display_name,repository_identity,created_at,updated_at)
                VALUES (?,?,?,?,?)
                """,
                (session_id, display_name or session_id, repository_identity, now, now),
            )
            connection.commit()

    def sdk_session(self, session_id: str) -> SQLiteSession:
        self.inspect(session_id)
        return SQLiteSession(session_id, self.database)

    def list(self) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT session_id,display_name,repository_identity,created_at,updated_at
                FROM skillshelf_session_metadata ORDER BY updated_at DESC
                """
            ).fetchall()
        return [dict(row) for row in rows]

    def inspect(self, session_id: str) -> dict[str, Any]:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT session_id,display_name,repository_identity,created_at,updated_at
                FROM skillshelf_session_metadata WHERE session_id=?
                """,
                (session_id,),
            ).fetchone()
        if row is None:
            raise KeyError(session_id)
        return dict(row)

    def add_pending_approval(self, session_id: str, approval_id: str) -> None:
        self.inspect(session_id)
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO skillshelf_pending_approvals(approval_id,session_id) VALUES (?,?)",
                (approval_id, session_id),
            )
            connection.commit()

    async def export(self, session_id: str, destination: Path) -> Path:
        session = self.sdk_session(session_id)
        try:
            history = await session.get_items()
        finally:
            session.close()
        payload = redact({"metadata": self.inspect(session_id), "history": history})
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        return destination

    def delete_sync(self, session_id: str) -> None:
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute("DELETE FROM agent_messages WHERE session_id=?", (session_id,))
            connection.execute("DELETE FROM agent_sessions WHERE session_id=?", (session_id,))
            connection.execute(
                "DELETE FROM skillshelf_session_artifacts WHERE session_id=? AND retained=0",
                (session_id,),
            )
            connection.execute(
                "DELETE FROM skillshelf_replay_checkpoints WHERE session_id=?", (session_id,)
            )
            connection.execute(
                "DELETE FROM skillshelf_pending_approvals WHERE session_id=?", (session_id,)
            )
            connection.execute(
                "DELETE FROM skillshelf_session_metadata WHERE session_id=?", (session_id,)
            )
            connection.commit()
        if not self.verify_deleted(session_id):
            raise RuntimeError("session deletion verification failed")

    async def delete(self, session_id: str, *, confirmed: bool) -> None:
        if not confirmed:
            raise ValueError("session deletion requires explicit confirmation")
        self.delete_sync(session_id)
        verification = SQLiteSession(session_id, self.database)
        try:
            if await verification.get_items():
                raise RuntimeError("SDK history remained after session deletion")
        finally:
            verification.close()

    def verify_deleted(self, session_id: str) -> bool:
        with self._connect() as connection:
            tables = (
                ("agent_messages", "session_id"),
                ("agent_sessions", "session_id"),
                ("skillshelf_session_metadata", "session_id"),
                ("skillshelf_pending_approvals", "session_id"),
                ("skillshelf_replay_checkpoints", "session_id"),
            )
            return all(
                connection.execute(
                    f"SELECT 1 FROM {table} WHERE {column}=? LIMIT 1", (session_id,)
                ).fetchone()
                is None
                for table, column in tables
            )

    def vacuum(self) -> None:
        with self._connect() as connection:
            connection.execute("VACUUM")
