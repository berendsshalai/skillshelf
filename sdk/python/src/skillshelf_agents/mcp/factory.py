from __future__ import annotations

from typing import Any

from agents.mcp import (
    MCPServerSse,
    MCPServerStdio,
    MCPServerStreamableHttp,
    create_static_tool_filter,
)
from agents.mcp.server import (
    MCPServerSseParams,
    MCPServerStdioParams,
    MCPServerStreamableHttpParams,
)

from .contracts import MCPServerDefinition


class MCPFactory:
    def create(self, definition: MCPServerDefinition) -> Any:
        common: dict[str, Any] = {
            "name": definition.name,
            "cache_tools_list": definition.cache_tools,
            "client_session_timeout_seconds": definition.client_session_timeout_seconds,
            "tool_filter": create_static_tool_filter(
                allowed_tool_names=definition.allowed_tools or None,
                blocked_tool_names=definition.blocked_tools or None,
            ),
            "require_approval": "always" if definition.require_approval else "never",
        }
        if definition.transport == "stdio":
            assert definition.command is not None
            params = MCPServerStdioParams(command=definition.command)
            if definition.args:
                params["args"] = definition.args
            if definition.env:
                params["env"] = definition.env
            if definition.cwd is not None:
                params["cwd"] = definition.cwd
            return MCPServerStdio(params=params, **common)
        assert definition.url is not None
        if definition.transport == "streamable_http":
            http_params = MCPServerStreamableHttpParams(url=definition.url)
            if definition.headers:
                http_params["headers"] = definition.headers
            return MCPServerStreamableHttp(params=http_params, **common)
        sse_params = MCPServerSseParams(url=definition.url)
        if definition.headers:
            sse_params["headers"] = definition.headers
        return MCPServerSse(params=sse_params, **common)
