"""Unified Agents SDK conversation and SkillShelf session metadata storage."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from .manager import UnifiedSessionManager


def scoped_session_id(repository: Path, supplied: str) -> str:
    from .identity import repository_identity

    prefix = hashlib.sha256(repository_identity(repository).encode()).hexdigest()[:12]
    return f"{prefix}:{supplied}"


class SessionStore:
    """Compatibility facade over the unified metadata table for the 0.2 CLI."""

    def __init__(self, path: Path) -> None:
        self.manager = UnifiedSessionManager(path)

    def ensure(self, session_id: str) -> None:
        try:
            self.manager.inspect(session_id)
        except KeyError:
            self.manager.create_with_id(session_id, repository_identity="legacy")

    def list(self) -> list[str]:
        return [item["session_id"] for item in self.manager.list()]

    def inspect(self, session_id: str) -> dict[str, Any]:
        return self.manager.inspect(session_id)

    def delete(self, session_id: str, *, confirmed: bool) -> None:
        if not confirmed:
            raise ValueError("session deletion requires explicit confirmation")
        # Compatibility callers are synchronous; delete metadata and SDK rows in one transaction.
        self.manager.delete_sync(session_id)

    def export(self, session_id: str, destination: Path) -> Path:
        metadata = self.inspect(session_id)
        destination.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
        return destination


__all__ = ["SessionStore", "UnifiedSessionManager", "scoped_session_id"]
