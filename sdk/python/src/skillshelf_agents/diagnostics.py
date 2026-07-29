from __future__ import annotations

import hashlib
import sys
from pathlib import Path
from typing import Any

from .mcp import MCPManager, MCPServerDefinition


async def run_fake_mcp_probe(repository_root: Path) -> dict[str, Any]:
    """Exercise connect, discovery, filtering, invocation and cleanup over real stdio MCP."""
    probe = "skillshelf-deep-doctor"
    expected_digest = hashlib.sha256(probe.encode("utf-8")).hexdigest()
    definition = MCPServerDefinition(
        name="offline-doctor",
        transport="stdio",
        command=sys.executable,
        args=[str(repository_root / "mcp" / "fake-server" / "server.py")],
        cwd=str(repository_root),
        allowed_tools=["read_probe"],
        tool_prefix="doctor",
        startup_timeout_seconds=30,
        call_timeout_seconds=15,
        client_session_timeout_seconds=15,
    )
    manager = MCPManager()
    manager.register(definition)
    connected = False
    payload: dict[str, Any] = {}
    try:
        await manager.connect_all()
        connected = True
        tools = await manager.list_tools()
        exposed = [tool.exposed_name for tool in tools]
        if exposed != ["doctor__read_probe"]:
            raise RuntimeError(f"unexpected filtered MCP tools: {exposed}")
        result = await manager.call_tool("doctor__read_probe", {"value": probe})
        rendered = str(result)
        if probe not in rendered or expected_digest not in rendered:
            raise RuntimeError("fake MCP result did not contain expected mechanical evidence")
        payload = {
            "status": "PASS",
            "connected": connected,
            "tools": exposed,
            "called": "doctor__read_probe",
            "evidence_sha256": expected_digest,
            "cleanup": "completed",
        }
    finally:
        await manager.cleanup()
    return payload
