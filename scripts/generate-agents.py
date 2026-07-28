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
DISCOVERY = ROOT / ".codex" / "agents"
MAINTENANCE_DEFINITIONS = ROOT / "agents" / "maintenance" / "definitions"
PROFILES = ("runtime", "maintenance", "all")


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


def runtime_outputs(*, include_discovery: bool = True) -> dict[pathlib.Path, str]:
    data = yaml.safe_load(REGISTRY.read_text(encoding="utf-8"))
    result: dict[pathlib.Path, str] = {}
    entries = [(data["master"], True), *((item, False) for item in data["agents"])]
    for item, is_master in entries:
        filename = f"{item['id']}.toml"
        content = render(item, master=is_master)
        result[GENERATED / "codex" / filename] = content
        if include_discovery:
            result[DISCOVERY / filename] = content
    result[GENERATED / "sdk" / "registry.json"] = json.dumps(data, indent=2) + "\n"
    return result


def maintenance_outputs(*, include_discovery: bool = True) -> dict[pathlib.Path, str]:
    result: dict[pathlib.Path, str] = {}
    for source in sorted(MAINTENANCE_DEFINITIONS.glob("*.toml")):
        content = source.read_text(encoding="utf-8")
        result[GENERATED / "maintenance" / source.name] = content
        if include_discovery:
            result[DISCOVERY / source.name] = content
    if len(result) // (2 if include_discovery else 1) != 8:
        raise ValueError("maintenance profile must contain exactly eight definitions")
    return result


def outputs(profile: str) -> dict[pathlib.Path, str]:
    if profile == "runtime":
        return runtime_outputs()
    if profile == "maintenance":
        return maintenance_outputs()
    return {**runtime_outputs(), **maintenance_outputs()}


def expected_discovery_names(profile: str) -> set[str]:
    names: set[str] = set()
    if profile in {"runtime", "all"}:
        names.update(path.name for path in runtime_outputs(include_discovery=False) if path.suffix == ".toml")
    if profile in {"maintenance", "all"}:
        names.update(path.name for path in maintenance_outputs(include_discovery=False))
    return names


def remove_stale_discovery(profile: str) -> None:
    DISCOVERY.mkdir(parents=True, exist_ok=True)
    expected = expected_discovery_names(profile)
    managed = (
        expected_discovery_names("runtime")
        | expected_discovery_names("maintenance")
    )
    for path in DISCOVERY.glob("*.toml"):
        if path.name in managed and path.name not in expected:
            path.unlink()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--profile", choices=PROFILES, default="runtime")
    args = parser.parse_args()
    drift = []
    selected = outputs(args.profile)
    for path, content in selected.items():
        if args.check:
            if not path.is_file() or path.read_text(encoding="utf-8") != content:
                drift.append(path.relative_to(ROOT).as_posix())
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8", newline="\n")
    expected = expected_discovery_names(args.profile)
    actual = {path.name for path in DISCOVERY.glob("*.toml")}
    managed = expected_discovery_names("runtime") | expected_discovery_names("maintenance")
    unexpected = sorted((actual & managed) - expected)
    if args.check and unexpected:
        drift.extend(f".codex/agents/{name} (unexpected for {args.profile})" for name in unexpected)
    elif not args.check:
        remove_stale_discovery(args.profile)
    if drift:
        print("generated agent drift: " + ", ".join(drift), file=sys.stderr)
        return 1
    count = len(expected)
    action = "validated" if args.check else "generated"
    print(f"{action} {count} {args.profile} agent definitions")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
