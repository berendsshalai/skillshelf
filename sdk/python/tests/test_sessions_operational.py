from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from skillshelf_agents.sessions.identity import repository_identity
from skillshelf_agents.sessions.manager import UnifiedSessionManager


def test_repository_identity_uses_normalized_remote_instead_of_local_path(tmp_path: Path) -> None:
    first = tmp_path / "first"
    second = tmp_path / "second"
    for root, remote in (
        (first, "git@github.com:Example/Repo.git"),
        (second, "https://github.com/example/repo/"),
    ):
        root.mkdir()
        subprocess.run(["git", "init", "-q"], cwd=root, check=True)
        subprocess.run(["git", "remote", "add", "origin", remote], cwd=root, check=True)

    assert repository_identity(first) == repository_identity(second)
    assert repository_identity(first) == "github.com/example/repo"


@pytest.mark.asyncio
async def test_unified_session_exports_redacted_history_and_verified_delete(tmp_path: Path) -> None:
    database = tmp_path / "sessions.sqlite"
    manager = UnifiedSessionManager(database)
    session_id = manager.create("demo", repository_identity="github.com/example/repo")
    sdk_session = manager.sdk_session(session_id)
    await sdk_session.add_items(
        [
            {
                "role": "user",
                "content": "Use bearer secret-token-value and sk-abcdefghijklmnop",
            }
        ]
    )
    manager.add_pending_approval(session_id, "approval-1")
    destination = tmp_path / "export.json"

    await manager.export(session_id, destination)
    exported = json.loads(destination.read_text(encoding="utf-8"))

    assert exported["metadata"]["repository_identity"] == "github.com/example/repo"
    assert "[REDACTED]" in json.dumps(exported)
    assert "secret-token-value" not in json.dumps(exported)

    await manager.delete(session_id, confirmed=True)

    assert await sdk_session.get_items() == []
    with pytest.raises(KeyError):
        manager.inspect(session_id)
    assert manager.verify_deleted(session_id)
    sdk_session.close()
