#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
    if not re.fullmatch(r"\d+\.\d+\.\d+", version):
        raise ValueError("VERSION must contain a semantic release version")
    observed = {
        "package.json": json.loads((ROOT / "package.json").read_text(encoding="utf-8"))["version"],
        ".codex-plugin/plugin.json": json.loads(
            (ROOT / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8")
        )["version"],
        "plugins/skillshelf/.codex-plugin/plugin.json": json.loads(
            (ROOT / "plugins" / "skillshelf" / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8")
        )["version"],
        "sdk/python/pyproject.toml": tomllib.loads(
            (ROOT / "sdk" / "python" / "pyproject.toml").read_text(encoding="utf-8")
        )["project"]["version"],
    }
    mismatches = {path: value for path, value in observed.items() if value != version}
    site = (ROOT / "site" / "index.html").read_text(encoding="utf-8")
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    if f"<strong>{version}</strong>" not in site:
        mismatches["site/index.html"] = "missing release stamp"
    if f"## [{version}]" not in changelog:
        mismatches["CHANGELOG.md"] = "missing release heading"
    if len(sys.argv) > 1 and sys.argv[1].startswith("v") and sys.argv[1] != f"v{version}":
        mismatches["git tag"] = sys.argv[1]
    if mismatches:
        print(json.dumps({"expected": version, "mismatches": mismatches}, indent=2), file=sys.stderr)
        return 1
    print(f"version consistency passed: {version}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
