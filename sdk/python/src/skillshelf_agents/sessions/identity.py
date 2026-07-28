from __future__ import annotations

import re
import subprocess
from pathlib import Path
from urllib.parse import urlparse


def _normalize_remote(remote: str) -> str:
    value = remote.strip()
    scp = re.fullmatch(r"(?:[^@]+@)?([^:]+):(.+)", value)
    if scp and "://" not in value:
        host, path = scp.groups()
    else:
        parsed = urlparse(value)
        host = parsed.hostname or ""
        path = parsed.path
    normalized_path = path.strip("/").removesuffix(".git")
    return f"{host.casefold()}/{normalized_path.casefold()}"


def repository_identity(
    repository_root: Path,
    *,
    project_id: str | None = None,
    root_marker: str | None = None,
) -> str:
    root = repository_root.expanduser().resolve()
    result = subprocess.run(
        ["git", "-C", str(root), "remote", "get-url", "origin"],
        capture_output=True,
        text=True,
        shell=False,
    )
    if result.returncode == 0 and result.stdout.strip():
        base = _normalize_remote(result.stdout)
    else:
        marker = root_marker if root_marker is not None else root.name
        base = f"local/{marker.casefold()}/{root.as_posix().casefold()}"
    if project_id:
        return f"{base}#{project_id.strip().casefold()}"
    return base
