from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Any

import pytest
from agents.mcp import MCPServerSse, MCPServerStdio, MCPServerStreamableHttp
from pydantic import ValidationError

from skillshelf_agents.mcp import (
    MCPFactory,
    MCPManager,
    MCPServerDefinition,
    MCPToolUnavailable,
)


class FakeServer:
    def __init__(
        self,
        tools: list[str],
        *,
        connect_delay: float = 0,
        call_delay: float = 0,
        fail_connect: bool = False,
    ) -> None:
        self.tools = tools
        self.connect_delay = connect_delay
        self.call_delay = call_delay
        self.fail_connect = fail_connect
        self.connected = False
        self.cleaned = False
        self.list_count = 0
        self.invalidated = False

    async def connect(self) -> None:
        await asyncio.sleep(self.connect_delay)
        if self.fail_connect:
            raise RuntimeError("connect failed")
        self.connected = True

    async def list_tools(self, *args: Any, **kwargs: Any) -> list[Any]:
        del args, kwargs
        self.list_count += 1
        return [SimpleNamespace(name=name, description=f"{name} tool") for name in self.tools]

    async def call_tool(
        self, tool_name: str, arguments: dict[str, Any] | None, meta: dict[str, Any] | None = None
    ) -> Any:
        del meta
        await asyncio.sleep(self.call_delay)
        return {"tool": tool_name, "arguments": arguments}

    def invalidate_tools_cache(self) -> None:
        self.invalidated = True

    async def cleanup(self) -> None:
        self.cleaned = True
        self.connected = False


def test_factory_returns_official_sdk_server_types() -> None:
    factory = MCPFactory()
    stdio = factory.create(
        MCPServerDefinition(name="local", transport="stdio", command="python", args=["server.py"])
    )
    http = factory.create(
        MCPServerDefinition(name="remote", transport="streamable_http", url="https://mcp.example")
    )
    sse = factory.create(
        MCPServerDefinition(name="legacy", transport="sse", url="https://mcp.example/sse")
    )

    assert isinstance(stdio, MCPServerStdio)
    assert isinstance(http, MCPServerStreamableHttp)
    assert isinstance(sse, MCPServerSse)


def test_definition_rejects_missing_transport_fields_and_insecure_http() -> None:
    with pytest.raises(ValidationError):
        MCPServerDefinition(name="bad", transport="stdio")
    with pytest.raises(ValidationError):
        MCPServerDefinition(name="bad", transport="streamable_http", url="http://public.example")


@pytest.mark.asyncio
async def test_manager_lifecycle_filters_prefixes_and_caches() -> None:
    server = FakeServer(["read", "write", "secret"])
    definition = MCPServerDefinition(
        name="repo",
        transport="stdio",
        command="unused",
        allowed_tools=["read", "write"],
        blocked_tools=["write"],
        tool_prefix="repo",
    )
    manager = MCPManager(factory=lambda _: server)
    manager.register(definition)

    await manager.connect_all()
    tools = await manager.list_tools()
    again = await manager.list_tools()

    assert [tool.exposed_name for tool in tools] == ["repo__read"]
    assert again == tools
    assert server.list_count == 1
    assert await manager.call_tool("repo__read", {"path": "README.md"}) == {
        "tool": "read",
        "arguments": {"path": "README.md"},
    }
    with pytest.raises(MCPToolUnavailable):
        await manager.call_tool("repo__secret", {})

    manager.invalidate_tools_cache("repo")
    assert server.invalidated
    await manager.list_tools()
    assert server.list_count == 2
    await manager.cleanup()
    assert server.cleaned


@pytest.mark.asyncio
async def test_manager_enforces_connect_and_call_timeouts_and_cleans_failures() -> None:
    slow_connect = FakeServer(["read"], connect_delay=0.05)
    connect_manager = MCPManager(factory=lambda _: slow_connect)
    connect_manager.register(
        MCPServerDefinition(
            name="slow-connect",
            transport="stdio",
            command="unused",
            startup_timeout_seconds=0.001,
        )
    )
    with pytest.raises(TimeoutError):
        await connect_manager.connect_all()
    assert slow_connect.cleaned

    slow_call = FakeServer(["read"], call_delay=0.05)
    call_manager = MCPManager(factory=lambda _: slow_call)
    call_manager.register(
        MCPServerDefinition(
            name="slow-call",
            transport="stdio",
            command="unused",
            call_timeout_seconds=0.001,
        )
    )
    await call_manager.connect_all()
    await call_manager.list_tools()
    with pytest.raises(TimeoutError):
        await call_manager.call_tool("slow-call__read", {})
    await call_manager.cleanup()


@pytest.mark.asyncio
async def test_partial_connect_failure_cleans_every_created_server() -> None:
    first = FakeServer(["one"])
    second = FakeServer(["two"], fail_connect=True)
    servers = iter([first, second])
    manager = MCPManager(factory=lambda _: next(servers))
    manager.register(MCPServerDefinition(name="one", transport="stdio", command="unused"))
    manager.register(MCPServerDefinition(name="two", transport="stdio", command="unused"))

    with pytest.raises(RuntimeError, match="connect failed"):
        await manager.connect_all()

    assert first.cleaned
    assert second.cleaned
