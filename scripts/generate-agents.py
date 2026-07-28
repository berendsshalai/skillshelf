#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import pathlib
import sys

import yaml

ROOT = pathlib.Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "agents" / "registry.yml"
GENERATED = ROOT / "agents" / "generated"


def toml_string(value: str) -> str:
    return '"""' + value.replace('"""', '\\"\\"\\"') + '"""'


def render(entry: dict, *, master: bool = False) -> str:
    name = entry["id"].replace("-", "_")
    instruction = (ROOT / entry["instruction_file"]).read_text(encoding="utf-8").strip()
    if master:
        body = (
            f"{instruction}\n\nRead agents/registry.yml. Select the smallest sufficient specialist set. "
            "Dispatch bounded native specialists, require structured reports, keep final user communication, "
            "record usage and meaningful governance events, and never paste every skill into parent context."
        )
        sandbox = "workspace-write"
        description = entry["description"]
    else:
        body = (
            f"{instruction}\n\nRequired skill: {entry['skill_path']}. Read that current SKILL.md before acting. "
            f"Allowed MCP: {', '.join(entry['allowed_mcp'])}. "
            f"Allowed capabilities: {', '.join(entry['allowed_capabilities'])}. "
            f"Prohibited: {', '.join(entry['prohibited_capabilities'])}. "
            f"Output contract: {entry['output_contract']}. Verify claims with evidence and return compact context."
        )
        sandbox = "workspace-write" if any(item.startswith("write_") for item in entry["allowed_capabilities"]) else "read-only"
        if sandbox == "read-only":
            body += " No write tools are permitted."
        description = entry["tool_description"]
    return (
        f'name = "{name}"\n'
        f"description = {json.dumps(description)}\n"
        f'sandbox_mode = "{sandbox}"\n'
        f"developer_instructions = {toml_string(body)}\n"
    )


def outputs() -> dict[pathlib.Path, str]:
    data = yaml.safe_load(REGISTRY.read_text(encoding="utf-8"))
    result: dict[pathlib.Path, str] = {}
    entries = [(data["master"], True), *((item, False) for item in data["agents"])]
    for item, is_master in entries:
        filename = f"{item['id']}.toml"
        content = render(item, master=is_master)
        result[GENERATED / "codex" / filename] = content
        result[ROOT / ".codex" / "agents" / filename] = content
    result[GENERATED / "sdk" / "registry.json"] = json.dumps(data, indent=2) + "\n"
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    drift = []
    for path, content in outputs().items():
        if args.check:
            if not path.is_file() or path.read_text(encoding="utf-8") != content:
                drift.append(path.relative_to(ROOT).as_posix())
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8", newline="\n")
    if drift:
        print("generated agent drift: " + ", ".join(drift), file=sys.stderr)
        return 1
    print("agent definitions valid" if args.check else "generated 6 Codex agents and SDK registry")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
