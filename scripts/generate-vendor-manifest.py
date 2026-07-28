#!/usr/bin/env python3
from __future__ import annotations
import hashlib, json, pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
files = {}
for path in sorted((ROOT / "vendor").rglob("*")):
    if path.is_file():
        rel = path.relative_to(ROOT).as_posix()
        files[rel] = hashlib.sha256(path.read_bytes()).hexdigest()
payload = {"algorithm": "sha256", "generated_from": "upstream-lock.json", "files": files}
(ROOT / "vendor-manifest.json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
print(f"hashed {len(files)} vendored files")
