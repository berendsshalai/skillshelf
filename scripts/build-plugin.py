#!/usr/bin/env python3
from __future__ import annotations
import json, pathlib, subprocess, sys, zipfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
subprocess.run([sys.executable, str(ROOT / "scripts/sync-plugin-tree.py")], check=True)
PACKAGE = ROOT / "plugins/skillshelf"
OUT = ROOT / "dist"
OUT.mkdir(exist_ok=True)
version = json.loads((PACKAGE / ".codex-plugin/plugin.json").read_text(encoding="utf-8"))["version"]
archive = OUT / f"skillshelf-{version}.zip"
with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as zf:
    for child in sorted(PACKAGE.rglob("*")):
        if child.is_file():
            zf.write(child, child.relative_to(PACKAGE).as_posix())
names = zipfile.ZipFile(archive).namelist()
if ".codex-plugin/plugin.json" not in names or len([x for x in names if x.startswith("skills/") and x.endswith("/SKILL.md") and x.count("/") == 2]) != 5:
    raise SystemExit("plugin archive structure invalid")
print(f"plugin archive built: {archive} ({len(names)} files)")
