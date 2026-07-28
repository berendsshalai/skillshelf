from pathlib import Path

from ..guardrails import validate_write


def authorised_path(path: Path, root: Path, *, approved: bool = False) -> Path:
    return validate_write(path, root, approved=approved)
