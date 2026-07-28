from __future__ import annotations

from typing import Literal
from urllib.parse import urlparse

from pydantic import BaseModel, Field, model_validator


class MCPServerDefinition(BaseModel):
    name: str = Field(min_length=1)
    transport: Literal["stdio", "streamable_http", "sse"]
    command: str | None = None
    args: list[str] = Field(default_factory=list)
    cwd: str | None = None
    env: dict[str, str] = Field(default_factory=dict)
    url: str | None = None
    headers: dict[str, str] = Field(default_factory=dict)
    allowed_tools: list[str] = Field(default_factory=list)
    blocked_tools: list[str] = Field(default_factory=list)
    tool_prefix: str | None = None
    cache_tools: bool = True
    require_approval: bool = False
    startup_timeout_seconds: float = Field(default=15, gt=0)
    call_timeout_seconds: float = Field(default=30, gt=0)
    client_session_timeout_seconds: float = Field(default=5, gt=0)

    @model_validator(mode="after")
    def validate_transport(self) -> "MCPServerDefinition":
        if self.transport == "stdio":
            if not self.command:
                raise ValueError("stdio transport requires command")
            if self.url is not None:
                raise ValueError("stdio transport does not accept url")
            return self
        if not self.url:
            raise ValueError(f"{self.transport} transport requires url")
        parsed = urlparse(self.url)
        if parsed.scheme not in {"https", "http"}:
            raise ValueError("MCP URL must use HTTP(S)")
        if parsed.scheme == "http" and parsed.hostname not in {"localhost", "127.0.0.1", "::1"}:
            raise ValueError("non-local MCP URLs must use HTTPS")
        if self.command is not None or self.args:
            raise ValueError(f"{self.transport} transport does not accept command or args")
        return self


class ManagedMCPTool(BaseModel):
    server_name: str
    original_name: str
    exposed_name: str
    description: str | None = None
