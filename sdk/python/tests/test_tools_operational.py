from __future__ import annotations

from pathlib import Path

import pytest

from skillshelf_agents.tools.artefacts import ArtifactStore
from skillshelf_agents.tools.filesystem import RepositoryFilesystem, RepositoryPathViolation
from skillshelf_agents.tools.registry import CapabilityToolRegistry
from skillshelf_agents.tools.subprocess import (
    SafeCommandExecutor,
    SafeCommandRequest,
    SafeCommandViolation,
)


def test_replacement_creates_backup_and_reports_independent_digests(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    target = root / "notes.txt"
    target.write_text("before", encoding="utf-8")
    filesystem = RepositoryFilesystem(root, tmp_path / "backups")

    result = filesystem.write_text_file("notes.txt", "after")

    assert target.read_text(encoding="utf-8") == "after"
    assert result.sha256_before == "6db7d803e74f1ffa7d8f5adc0bf95b3e15bf4c8373fffadf546227cc6c6742cb"
    assert result.sha256_after == "f39592393ef0859cb196a52693d2cea00fb2df784b3c04ae54aa7cadb8e562f8"
    assert result.backup_path is not None
    assert Path(result.backup_path).read_text(encoding="utf-8") == "before"


def test_repository_policy_rejects_vendor_submodule_and_escape(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    (root / "vendor").mkdir(parents=True)
    (root / "third_party" / "dependency").mkdir(parents=True)
    (root / ".gitmodules").write_text(
        '[submodule "dep"]\n\tpath = third_party/dependency\n\turl = https://example.test/dep.git\n',
        encoding="utf-8",
    )
    filesystem = RepositoryFilesystem(root, tmp_path / "backups")

    for path in ("vendor/file.txt", "third_party/dependency/file.txt", "../escape.txt"):
        with pytest.raises(RepositoryPathViolation):
            filesystem.write_text_file(path, "blocked")


def test_repository_policy_rejects_symlink_escape_when_supported(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    outside = tmp_path / "outside"
    root.mkdir()
    outside.mkdir()
    link = root / "linked"
    try:
        link.symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip("symlink creation unavailable on this Windows host")

    with pytest.raises(RepositoryPathViolation):
        RepositoryFilesystem(root, tmp_path / "backups").write_text_file("linked/file.txt", "blocked")


def test_safe_command_uses_argv_without_shell_and_records_artifacts(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    artifacts = ArtifactStore(tmp_path / "artifacts")
    executor = SafeCommandExecutor(root, artifacts)

    result = executor.run(
        SafeCommandRequest(executable="python", arguments=["--version"], cwd=".", timeout_seconds=30)
    )

    assert result.exit_code == 0
    assert result.command_digest
    assert result.duration_seconds >= 0
    assert artifacts.path_for(result.stdout_artifact_id).is_file()
    assert artifacts.path_for(result.stderr_artifact_id).is_file()


@pytest.mark.parametrize(
    ("executable", "arguments"),
    [
        ("git", ["reset", "--hard"]),
        ("git", ["push", "--force"]),
        ("python", ["script.py", ";", "whoami"]),
    ],
)
def test_safe_command_rejects_destructive_or_shell_syntax(
    tmp_path: Path,
    executable: str,
    arguments: list[str],
) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    executor = SafeCommandExecutor(root, ArtifactStore(tmp_path / "artifacts"))

    with pytest.raises(SafeCommandViolation):
        executor.run(
            SafeCommandRequest(
                executable=executable,
                arguments=arguments,
                cwd=".",
                timeout_seconds=30,
            )
        )


def test_capability_registry_returns_real_sdk_function_tools(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    registry = CapabilityToolRegistry(
        filesystem=RepositoryFilesystem(root, tmp_path / "backups"),
        commands=SafeCommandExecutor(root, ArtifactStore(tmp_path / "artifacts")),
    )

    tools = registry.build(["read_files", "run_safe_commands"])

    assert {tool.name for tool in tools} == {
        "list_directory",
        "read_binary_metadata",
        "read_text_file",
        "search_text",
        "run_safe_command",
    }
    with pytest.raises(KeyError):
        registry.build(["unregistered_capability"])
