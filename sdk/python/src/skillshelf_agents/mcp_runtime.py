from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class MCPServerDefinition:
    name: str
    transport: str
    read_tools: tuple[str, ...]
    write_tools: tuple[str, ...]
    confirmation_required: bool
    validation_command: str
    installation_status: str


class MCPRuntime:
    def __init__(self, root: Path) -> None:
        raw = yaml.safe_load((root / "mcp" / "registry.yml").read_text(encoding="utf-8"))
        self.servers = {item["name"]: MCPServerDefinition(
            item["name"], item["transport"], tuple(item["read_tools"]), tuple(item["write_tools"]),
            bool(item["confirmation_required"]), item["validation_command"], item["installation_status"])
            for item in raw["servers"]}
        self._tool_cache: dict[str, tuple[str, ...]] = {}

    def assigned(self, names: list[str]) -> list[MCPServerDefinition]:
        unknown = set(names) - self.servers.keys()
        if unknown:
            raise ValueError(f"unknown MCP servers: {sorted(unknown)}")
        return [self.servers[name] for name in names]

    def tools(self, server: str, *, include_writes: bool = False, approved: bool = False) -> tuple[str, ...]:
        definition = self.servers[server]
        tools = list(definition.read_tools)
        if include_writes:
            if definition.confirmation_required and not approved:
                raise PermissionError("MCP write tools require explicit approval")
            tools.extend(definition.write_tools)
        result = tuple(tools)
        self._tool_cache[server] = result
        return result

    def permissions(self, names: list[str]) -> dict[str, dict[str, Any]]:
        return {item.name: {"read": item.read_tools, "write": item.write_tools,
                            "approval_required": item.confirmation_required} for item in self.assigned(names)}

    def health(self) -> dict[str, str]:
        return {name: ("PASS" if item.installation_status in {"built-in", "host-provided"} else "SKIPPED")
                for name, item in self.servers.items()}

    async def close(self) -> None:
        self._tool_cache.clear()
