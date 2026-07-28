from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import time
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from .artefacts import ArtifactStore


class SafeCommandViolation(PermissionError):
    pass


class SafeCommandRequest(BaseModel):
    executable: Literal["python", "pytest", "node", "npm", "git", "ruff", "mypy"]
    arguments: list[str] = Field(default_factory=list, max_length=100)
    cwd: str
    timeout_seconds: int = Field(default=60, ge=1, le=600)


class SafeCommandResult(BaseModel):
    exit_code: int
    stdout_artifact_id: str
    stderr_artifact_id: str
    duration_seconds: float
    command_digest: str
    working_directory: str


class SafeCommandExecutor:
    _SHELL_META = frozenset({"&", "|", ";", "<", ">", "&&", "||"})

    def __init__(self, repository_root: Path, artifacts: ArtifactStore) -> None:
        self.repository_root = repository_root.resolve()
        self.artifacts = artifacts

    def _cwd(self, relative: str) -> Path:
        candidate = (self.repository_root / relative).resolve()
        try:
            candidate.relative_to(self.repository_root)
        except ValueError as exc:
            raise SafeCommandViolation("command working directory escapes repository") from exc
        if not candidate.is_dir():
            raise NotADirectoryError(relative)
        return candidate

    @classmethod
    def _validate_arguments(cls, request: SafeCommandRequest) -> None:
        if any(argument in cls._SHELL_META or any(char in argument for char in "\r\n") for argument in request.arguments):
            raise SafeCommandViolation("shell syntax is forbidden; commands must use literal argv")
        lowered = [argument.casefold() for argument in request.arguments]
        if request.executable == "git":
            joined = " ".join(lowered)
            forbidden = (
                "reset --hard",
                "push --force",
                "push -f",
                "credential",
                "clean -fd",
                "clean -df",
            )
            if any(value in joined for value in forbidden):
                raise SafeCommandViolation("destructive or credential-related Git command is forbidden")
        if any(value in {"rm", "rmdir", "del", "remove-item"} for value in lowered):
            raise SafeCommandViolation("recursive deletion commands are forbidden")

    def run(self, request: SafeCommandRequest) -> SafeCommandResult:
        self._validate_arguments(request)
        cwd = self._cwd(request.cwd)
        executable = shutil.which(request.executable)
        if executable is None:
            raise FileNotFoundError(request.executable)
        argv = [executable, *request.arguments]
        digest = hashlib.sha256(
            json.dumps(
                {"executable": request.executable, "arguments": request.arguments, "cwd": str(cwd)},
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()
        started = time.monotonic()
        try:
            completed = subprocess.run(
                argv,
                cwd=cwd,
                capture_output=True,
                timeout=request.timeout_seconds,
                shell=False,
            )
            exit_code = completed.returncode
            stdout = completed.stdout
            stderr = completed.stderr
        except subprocess.TimeoutExpired as exc:
            exit_code = 124
            stdout = exc.stdout or b""
            stderr = (exc.stderr or b"") + b"\ncommand timed out"
        duration = time.monotonic() - started
        stdout_artifact = self.artifacts.store_bytes(stdout, suffix=".stdout.txt", media_type="text/plain")
        stderr_artifact = self.artifacts.store_bytes(stderr, suffix=".stderr.txt", media_type="text/plain")
        return SafeCommandResult(
            exit_code=exit_code,
            stdout_artifact_id=stdout_artifact.artifact_id,
            stderr_artifact_id=stderr_artifact.artifact_id,
            duration_seconds=duration,
            command_digest=digest,
            working_directory=str(cwd),
        )
