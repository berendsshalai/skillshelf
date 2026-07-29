#!/usr/bin/env python3
"""Deterministic local MCP provider used by deep diagnostics and integration tests."""

from __future__ import annotations

import hashlib

from mcp.server.fastmcp import FastMCP

server = FastMCP("skillshelf-fake")


@server.tool(description="Return deterministic read-only evidence for a diagnostic probe.")
def read_probe(value: str) -> dict[str, str]:
    """Echo a bounded value and its SHA-256 digest without external side effects."""
    if len(value) > 4096:
        raise ValueError("probe value exceeds 4096 characters")
    return {
        "value": value,
        "sha256": hashlib.sha256(value.encode("utf-8")).hexdigest(),
        "provider": "skillshelf-fake",
    }


@server.tool(description="Return the fake provider's fixed capability declaration.")
def capabilities() -> dict[str, object]:
    """Describe the deterministic provider used by offline diagnostics."""
    return {
        "read_only": True,
        "network": False,
        "tools": ["read_probe", "capabilities"],
    }


if __name__ == "__main__":
    server.run(transport="stdio")
