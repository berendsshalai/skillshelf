from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import Any

from .contracts import MCPServerDefinition, ManagedMCPTool
from .factory import MCPFactory


class MCPToolUnavailable(LookupError):
    pass


class MCPManager:
    def __init__(self, factory: Callable[[MCPServerDefinition], Any] | None = None) -> None:
        sdk_factory = MCPFactory()
        self._factory = factory or sdk_factory.create
        self._definitions: dict[str, MCPServerDefinition] = {}
        self._servers: dict[str, Any] = {}
        self._cache: dict[str, list[ManagedMCPTool]] = {}
        self._tool_index: dict[str, ManagedMCPTool] = {}

    @property
    def servers(self) -> list[Any]:
        return list(self._servers.values())

    def register(self, definition: MCPServerDefinition) -> None:
        if definition.name in self._definitions:
            raise ValueError(f"duplicate MCP server name: {definition.name}")
        self._definitions[definition.name] = definition
        self._servers[definition.name] = self._factory(definition)

    async def connect_all(self) -> None:
        try:
            for name, server in self._servers.items():
                timeout = self._definitions[name].startup_timeout_seconds
                await asyncio.wait_for(server.connect(), timeout=timeout)
        except BaseException:
            await self.cleanup()
            raise

    async def list_tools(self) -> list[ManagedMCPTool]:
        discovered: list[ManagedMCPTool] = []
        index: dict[str, ManagedMCPTool] = {}
        for name, server in self._servers.items():
            definition = self._definitions[name]
            tools = self._cache.get(name)
            if tools is None:
                raw_tools = await asyncio.wait_for(
                    server.list_tools(),
                    timeout=definition.call_timeout_seconds,
                )
                tools = []
                allowed = set(definition.allowed_tools)
                blocked = set(definition.blocked_tools)
                prefix = definition.tool_prefix or definition.name
                for raw in raw_tools:
                    original = raw.name
                    if (allowed and original not in allowed) or original in blocked:
                        continue
                    tools.append(
                        ManagedMCPTool(
                            server_name=name,
                            original_name=original,
                            exposed_name=f"{prefix}__{original}",
                            description=getattr(raw, "description", None),
                        )
                    )
                if definition.cache_tools:
                    self._cache[name] = tools
            for tool in tools:
                if tool.exposed_name in index:
                    raise ValueError(f"MCP tool name collision: {tool.exposed_name}")
                index[tool.exposed_name] = tool
                discovered.append(tool)
        self._tool_index = index
        return discovered

    async def call_tool(
        self,
        exposed_name: str,
        arguments: dict[str, Any] | None,
        *,
        meta: dict[str, Any] | None = None,
    ) -> Any:
        if exposed_name not in self._tool_index:
            await self.list_tools()
        tool = self._tool_index.get(exposed_name)
        if tool is None:
            raise MCPToolUnavailable(exposed_name)
        definition = self._definitions[tool.server_name]
        server = self._servers[tool.server_name]
        return await asyncio.wait_for(
            server.call_tool(tool.original_name, arguments, meta=meta),
            timeout=definition.call_timeout_seconds,
        )

    def invalidate_tools_cache(self, server_name: str | None = None) -> None:
        names = [server_name] if server_name is not None else list(self._servers)
        for name in names:
            if name not in self._servers:
                raise KeyError(name)
            self._cache.pop(name, None)
            invalidate = getattr(self._servers[name], "invalidate_tools_cache", None)
            if invalidate is not None:
                invalidate()
        self._tool_index.clear()

    async def cleanup(self) -> None:
        errors: list[Exception] = []
        for server in reversed(list(self._servers.values())):
            try:
                await server.cleanup()
            except Exception as exc:
                errors.append(exc)
        self._cache.clear()
        self._tool_index.clear()
        if errors:
            raise ExceptionGroup("MCP cleanup failures", errors)

    async def __aenter__(self) -> "MCPManager":
        await self.connect_all()
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        await self.cleanup()
