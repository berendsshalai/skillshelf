from __future__ import annotations

from pathlib import Path

from .artefacts import ArtifactStore
from .subprocess import SafeCommandExecutor, SafeCommandRequest, SafeCommandResult


def inspect_git(repository_root: Path, arguments: list[str], artifacts: ArtifactStore) -> SafeCommandResult:
    return SafeCommandExecutor(repository_root, artifacts).run(
        SafeCommandRequest(executable="git", arguments=arguments, cwd=".", timeout_seconds=60)
    )
