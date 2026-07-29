from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import socket
import stat
import tempfile
import time
import uuid
from pathlib import Path
from typing import Any

SAFE_IDENTIFIER = re.compile(r"^[a-z0-9][a-z0-9._-]{0,127}$")
SAFE_PROPOSAL_ID = re.compile(r"^proposal-[a-z0-9][a-z0-9-]{5,63}$")
SHA256 = re.compile(r"^[0-9a-f]{64}$")
REFERENCE = re.compile(r"(?<![A-Za-z0-9_.-])((?:references|scripts|assets|tests)/[A-Za-z0-9_./-]+)")
REQUIRED_FILES = (
    "SKILL.md",
    "README.md",
    "PROVENANCE.yml",
    "SEMANTIC_CONTRACT.yml",
    "UPSTREAM_DIFF.md",
)
PACKAGE_DIRECTORIES = ("references", "scripts", "assets", "tests")
IGNORED_ARTIFACT = re.compile(r"(^|/)(?:__pycache__|\.DS_Store)(?:/|$)|\.pyc$|(^|/)\.~lock\.")


class SafetyError(RuntimeError):
    pass


def utc_now() -> str:
    from datetime import UTC, datetime

    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def ensure_relative_to(root: Path, candidate: Path) -> Path:
    boundary = root.resolve(strict=False)
    resolved = candidate.resolve(strict=False)
    try:
        resolved.relative_to(boundary)
    except ValueError as exc:
        raise SafetyError(f"path escapes boundary: {candidate}") from exc
    return resolved


def is_link_or_reparse(path: Path) -> bool:
    if path.is_symlink():
        return True
    try:
        attributes = getattr(os.lstat(path), "st_file_attributes", 0)
    except OSError:
        return False
    return bool(attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT)


def validate_package(package: Path, *, create_missing_directories: bool = False) -> dict[str, str]:
    package = package.resolve(strict=True)
    if not package.is_dir() or is_link_or_reparse(package):
        raise SafetyError(f"package must be a real directory: {package}")
    missing = [name for name in REQUIRED_FILES if not (package / name).is_file()]
    if missing:
        raise SafetyError(f"package is missing required files: {', '.join(missing)}")
    for directory in PACKAGE_DIRECTORIES:
        target = package / directory
        if not target.exists() and create_missing_directories:
            target.mkdir()
        if not target.is_dir() or is_link_or_reparse(target):
            raise SafetyError(f"package directory is missing or unsafe: {directory}")

    manifest: dict[str, str] = {}
    for path in sorted(package.rglob("*")):
        if is_link_or_reparse(path):
            raise SafetyError(f"links and reparse points are unsupported: {path}")
        relative = path.relative_to(package).as_posix()
        if IGNORED_ARTIFACT.search(relative):
            raise SafetyError(f"build artifact is not allowed: {relative}")
        if path.is_dir():
            manifest[f"{relative}/"] = "directory"
        elif path.is_file():
            manifest[relative] = hashlib.sha256(path.read_bytes()).hexdigest()
        else:
            raise SafetyError(f"unsupported package path type: {relative}")

    text = (package / "SKILL.md").read_text(encoding="utf-8")
    missing_references = sorted(
        {
            match.group(1).rstrip(").,;:`")
            for match in REFERENCE.finditer(text)
            if match.group(1).rstrip(").,;:`") not in manifest
        }
    )
    if missing_references:
        raise SafetyError(f"missing referenced files: {', '.join(missing_references)}")
    return manifest


def package_digest(package: Path, *, create_missing_directories: bool = False) -> str:
    manifest = validate_package(package, create_missing_directories=create_missing_directories)
    digest = hashlib.sha256()
    for name, value in sorted(manifest.items()):
        digest.update(f"{name}\0{value}\n".encode())
    return digest.hexdigest()


def atomic_replace(source: Path, destination: Path, timeout: float = 5.0) -> None:
    deadline = time.monotonic() + timeout
    while True:
        try:
            os.replace(source, destination)
            return
        except PermissionError:
            if time.monotonic() >= deadline:
                raise
            time.sleep(0.025)


def atomic_write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    file_descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    temporary_path = Path(temporary)
    try:
        with os.fdopen(file_descriptor, "w", encoding="utf-8", newline="\n") as stream:
            json.dump(value, stream, indent=2, sort_keys=True)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        atomic_replace(temporary_path, path)
    finally:
        temporary_path.unlink(missing_ok=True)


def read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SafetyError(f"cannot read valid JSON: {path}") from exc
    if not isinstance(value, dict):
        raise SafetyError(f"JSON object required: {path}")
    return value


def copy_package(source: Path, destination: Path) -> None:
    if destination.exists():
        raise SafetyError(f"destination already exists: {destination}")
    temporary = destination.with_name(f".{destination.name}.{uuid.uuid4().hex}.tmp")
    try:
        shutil.copytree(source, temporary, copy_function=shutil.copy2)
        atomic_replace(temporary, destination)
    finally:
        if temporary.exists():
            shutil.rmtree(temporary)


def remove_tree(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path)


class OwnedFileLock:
    def __init__(self, path: Path, *, timeout: float = 30.0) -> None:
        self.path = path
        self.timeout = timeout
        self.token = uuid.uuid4().hex

    def __enter__(self) -> "OwnedFileLock":
        self.path.parent.mkdir(parents=True, exist_ok=True)
        deadline = time.monotonic() + self.timeout
        payload = json.dumps(
            {
                "token": self.token,
                "pid": os.getpid(),
                "host": socket.gethostname(),
                "created_at": utc_now(),
            },
            sort_keys=True,
        ).encode()
        while True:
            try:
                descriptor = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
                with os.fdopen(descriptor, "wb") as stream:
                    stream.write(payload)
                    stream.flush()
                    os.fsync(stream.fileno())
                return self
            except (FileExistsError, PermissionError):
                if time.monotonic() >= deadline:
                    raise SafetyError(f"timed out acquiring lock: {self.path.name}")
                time.sleep(0.025)

    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> None:
        try:
            current = read_json(self.path)
            if current.get("token") == self.token:
                self.path.unlink()
        except FileNotFoundError:
            return


def binding_digest(fields: dict[str, str]) -> str:
    return hashlib.sha256(json.dumps(fields, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
