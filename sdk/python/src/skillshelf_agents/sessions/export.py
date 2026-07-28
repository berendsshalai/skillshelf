from __future__ import annotations

from pathlib import Path

from .manager import UnifiedSessionManager


async def export_session(manager: UnifiedSessionManager, session_id: str, destination: Path) -> Path:
    return await manager.export(session_id, destination)
