#!/usr/bin/env python3
from __future__ import annotations
import pathlib
import shutil

ROOT = pathlib.Path(__file__).resolve().parents[1]
source, output = ROOT / "site", ROOT / "_site"
if output.exists():
    shutil.rmtree(output)
shutil.copytree(source, output)
required = ["index.html", "skills/index.html", "architecture/index.html", "installation/index.html",
            "provenance/index.html", "agents/index.html", "mcp/index.html", "credits/index.html",
            "socials/index.html", "assets/styles.css", "assets/og.png"]
for rel in required:
    if not (output / rel).is_file():
        raise SystemExit(f"missing built site file: {rel}")
print(f"site built at {output} ({len(required)} required artifacts verified)")
