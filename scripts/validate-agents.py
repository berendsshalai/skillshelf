#!/usr/bin/env python3
from __future__ import annotations

import pathlib
import subprocess
import sys
import tomllib

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "sdk" / "python" / "src"))

from skillshelf_agents.mcp_runtime import MCPRuntime  # noqa: E402
from skillshelf_agents.registry import RuntimeRegistry  # noqa: E402
from skillshelf_agents.skill_loader import SkillLoader  # noqa: E402


def main() -> int:
    registry = RuntimeRegistry.load(ROOT)
    summaries = SkillLoader(ROOT).discover()
    if len(summaries) != 5:
        raise AssertionError("exactly five skills required")
    if len(MCPRuntime(ROOT).servers) < 9:
        raise AssertionError("MCP policy aliases missing")
    generated = list((ROOT / "agents" / "generated" / "codex").glob("*.toml"))
    if len(generated) != 6:
        raise AssertionError("six generated Codex agents required")
    for path in generated:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
        if not all(data.get(key) for key in ("name", "description", "developer_instructions")):
            raise AssertionError(f"invalid Codex agent: {path}")
    result = subprocess.run([sys.executable, str(ROOT / "scripts" / "generate-agents.py"), "--check"])
    if result.returncode:
        return result.returncode
    print(f"agent runtime validation passed: 1 master, {len(registry.agents)} specialists")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
