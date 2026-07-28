#!/usr/bin/env python3
from __future__ import annotations

import os
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
VENV_PYTHON = ROOT / "sdk" / "python" / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
PYTHON = VENV_PYTHON if VENV_PYTHON.is_file() else pathlib.Path(sys.executable)


def run(*args: str) -> None:
    result = subprocess.run([str(PYTHON), "-m", "skillshelf_agents", *args], cwd=ROOT)
    if result.returncode:
        raise SystemExit(result.returncode)


run("--help")
run("agents", "--json")
run("doctor", "--json")
run("mcp", "permissions", "memory-agent")
run("route", "what did we decide last week?")
print("offline agent smoke tests passed; no model call made")
