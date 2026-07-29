from __future__ import annotations

from pathlib import Path

import pytest

from skillshelf_agents.diagnostics import run_fake_mcp_probe


@pytest.mark.asyncio
async def test_bundled_fake_mcp_proves_real_stdio_lifecycle() -> None:
    root = Path(__file__).resolve().parents[3]
    result = await run_fake_mcp_probe(root)

    assert result["status"] == "PASS"
    assert result["connected"] is True
    assert result["tools"] == ["doctor__read_probe"]
    assert result["called"] == "doctor__read_probe"
    assert len(result["evidence_sha256"]) == 64
    assert result["cleanup"] == "completed"
