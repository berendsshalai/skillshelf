#!/usr/bin/env python3
from __future__ import annotations
import hashlib
import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
files = {}

def canonical_bytes(path):
    data = path.read_bytes()
    if b"\0" not in data:
        try:
            data.decode("utf-8")
            return data.replace(b"\r\n", b"\n")
        except UnicodeDecodeError:
            pass
    return data

for path in sorted((ROOT / "vendor").rglob("*")):
    if path.is_file():
        rel = path.relative_to(ROOT).as_posix()
        files[rel] = hashlib.sha256(canonical_bytes(path)).hexdigest()
payload = {
    "algorithm": "sha256",
    "text_normalization": "utf8-crlf-to-lf",
    "generated_from": "upstream-lock.json",
    "files": files,
}
(ROOT / "vendor-manifest.json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
print(f"hashed {len(files)} vendored files")
