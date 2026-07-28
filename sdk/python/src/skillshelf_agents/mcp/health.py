from __future__ import annotations

from pydantic import BaseModel


class MCPHealth(BaseModel):
    server_name: str
    connected: bool
    tool_count: int = 0
    error: str | None = None
