from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path
from typing import Any


def scoped_session_id(repository: Path, supplied: str) -> str:
    prefix = hashlib.sha256(str(repository.resolve()).encode()).hexdigest()[:12]
    return f"{prefix}:{supplied}"


class SessionStore:
    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        with sqlite3.connect(path) as db:
            db.execute(
                "CREATE TABLE IF NOT EXISTS sessions (id TEXT PRIMARY KEY, state TEXT NOT NULL DEFAULT '{}')"
            )

    def ensure(self, session_id: str) -> None:
        with sqlite3.connect(self.path) as db:
            db.execute("INSERT OR IGNORE INTO sessions(id) VALUES (?)", (session_id,))

    def list(self) -> list[str]:
        with sqlite3.connect(self.path) as db:
            return [row[0] for row in db.execute("SELECT id FROM sessions ORDER BY id")]

    def inspect(self, session_id: str) -> dict[str, Any]:
        with sqlite3.connect(self.path) as db:
            row = db.execute("SELECT state FROM sessions WHERE id=?", (session_id,)).fetchone()
        if row is None:
            raise KeyError(session_id)
        return {"id": session_id, "state": json.loads(row[0])}

    def delete(self, session_id: str, *, confirmed: bool) -> None:
        if not confirmed:
            raise ValueError("session deletion requires explicit confirmation")
        with sqlite3.connect(self.path) as db:
            db.execute("DELETE FROM sessions WHERE id=?", (session_id,))

    def export(self, session_id: str, destination: Path) -> Path:
        destination.write_text(json.dumps(self.inspect(session_id), indent=2) + "\n", encoding="utf-8")
        return destination
