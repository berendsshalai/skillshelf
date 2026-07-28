#!/usr/bin/env python3
"""Build the canonical repo-marketplace plugin tree from root authoring sources."""
from __future__ import annotations
import filecmp, pathlib, shutil

ROOT = pathlib.Path(__file__).resolve().parents[1]
TARGET = ROOT / "plugins/skillshelf"
SOURCES = [".codex-plugin", "skills", "vendor"]
FILES = ["LICENSE", "THIRD_PARTY_NOTICES.md", "ARCHITECTURE.md", "SECURITY.md",
         "upstream-lock.json", "vendor-manifest.json"]

if TARGET.exists():
    resolved = TARGET.resolve()
    expected_parent = (ROOT / "plugins").resolve()
    if resolved.parent != expected_parent or resolved.name != "skillshelf":
        raise SystemExit(f"refusing to replace unexpected target: {resolved}")
    shutil.rmtree(TARGET)
TARGET.mkdir(parents=True)
for name in SOURCES:
    shutil.copytree(ROOT / name, TARGET / name)
for name in FILES:
    shutil.copy2(ROOT / name, TARGET / name)
(TARGET / "README.md").write_text(
    "# SkillShelf plugin package\n\n"
    "Generated from the repository root by `scripts/sync-plugin-tree.py`. "
    "Edit the root authoring sources, not this package mirror.\n",
    encoding="utf-8",
)
print(f"canonical plugin tree synchronized: {TARGET}")
