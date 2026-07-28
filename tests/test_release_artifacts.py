from __future__ import annotations

import gzip
import hashlib
import io
import json
import subprocess
import sys
import tarfile
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
VALIDATOR = ROOT / "scripts" / "validate-release.py"
VERSION = "0.3.0"
WHEEL_NAME = f"skillshelf_agents-{VERSION}-py3-none-any.whl"
SDIST_NAME = f"skillshelf_agents-{VERSION}.tar.gz"
RUNTIME_FILES = (
    "agents/registry.yml",
    "agents/registry.schema.json",
    "scripts/install-agent-runtime.ps1",
    "scripts/install-agent-runtime.sh",
    "scripts/uninstall-agent-runtime.ps1",
    "scripts/uninstall-agent-runtime.sh",
    "LICENSE",
    "THIRD_PARTY_NOTICES.md",
    "VERSION",
)
RUNTIME_DIRECTORY_FILES = (
    "agents/instructions/skillshelf-master.md",
    "agents/generated/codex/skillshelf-master.toml",
    "mcp/registry.yml",
    "docs/agents/OVERVIEW.md",
    "docs/integrations/DEPLOYMENT.md",
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_zip(path: Path, entries: dict[str, bytes | str]) -> None:
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, content in sorted(entries.items()):
            info = zipfile.ZipInfo(name, date_time=(2020, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            payload = content.encode("utf-8") if isinstance(content, str) else content
            archive.writestr(info, payload)


def _write_sdist(path: Path, *, package_version: str = VERSION) -> None:
    root = f"skillshelf_agents-{VERSION}"
    entries = {
        f"{root}/PKG-INFO": (
            "Metadata-Version: 2.4\n"
            "Name: skillshelf-agents\n"
            f"Version: {package_version}\n\n"
        ).encode(),
        f"{root}/pyproject.toml": (
            "[project]\n"
            'name = "skillshelf-agents"\n'
            f'version = "{package_version}"\n'
        ).encode(),
    }
    with path.open("wb") as raw:
        with gzip.GzipFile(fileobj=raw, mode="wb", mtime=0) as compressed:
            with tarfile.open(fileobj=compressed, mode="w") as archive:
                for name, payload in sorted(entries.items()):
                    info = tarfile.TarInfo(name)
                    info.size = len(payload)
                    info.mtime = 0
                    info.mode = 0o644
                    archive.addfile(info, io.BytesIO(payload))


def _write_repository(repository: Path) -> None:
    contents = {
        "agents/registry.yml": "agents: []\n",
        "agents/registry.schema.json": "{}\n",
        "scripts/install-agent-runtime.ps1": "Write-Output install\n",
        "scripts/install-agent-runtime.sh": "#!/bin/sh\n",
        "scripts/uninstall-agent-runtime.ps1": "Write-Output uninstall\n",
        "scripts/uninstall-agent-runtime.sh": "#!/bin/sh\n",
        "LICENSE": "MIT\n",
        "THIRD_PARTY_NOTICES.md": "SkillShelf\n",
        "VERSION": f"{VERSION}\n",
        "agents/instructions/skillshelf-master.md": "# Master\n",
        "agents/generated/codex/skillshelf-master.toml": 'name = "master"\n',
        "mcp/registry.yml": "servers: []\n",
        "docs/agents/OVERVIEW.md": "# Agents\n",
        "docs/integrations/DEPLOYMENT.md": "# Deployment\n",
    }
    for relative, content in contents.items():
        target = repository / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")


def _write_plugin(
    path: Path,
    *,
    manifest_version: str = VERSION,
) -> None:
    entries: dict[str, str] = {
        ".codex-plugin/plugin.json": json.dumps(
            {"name": "skillshelf", "version": manifest_version},
            sort_keys=True,
        )
    }
    for name in ("find", "superpowers", "memory", "design", "governor"):
        entries[f"skills/{name}/SKILL.md"] = f"# {name}\n"
    _write_zip(path, entries)


def _write_wheel(path: Path) -> None:
    dist_info = f"skillshelf_agents-{VERSION}.dist-info"
    _write_zip(
        path,
        {
            "skillshelf_agents/__init__.py": f'__version__ = "{VERSION}"\n',
            f"{dist_info}/METADATA": (
                "Metadata-Version: 2.4\n"
                "Name: skillshelf-agents\n"
                f"Version: {VERSION}\n\n"
            ),
            f"{dist_info}/WHEEL": (
                "Wheel-Version: 1.0\n"
                "Generator: fixture\n"
                "Root-Is-Purelib: true\n"
                "Tag: py3-none-any\n"
            ),
            f"{dist_info}/RECORD": "",
        },
    )


def _runtime_entries(
    repository: Path,
    wheel: Path,
    *,
    omit: str | None = None,
) -> dict[str, bytes]:
    members: dict[str, bytes] = {}
    for relative in (*RUNTIME_FILES, *RUNTIME_DIRECTORY_FILES):
        if relative != omit:
            members[relative] = (repository / relative).read_bytes()
    members[f"sdk/python/dist/{wheel.name}"] = wheel.read_bytes()
    return members


def _refresh_metadata(release: Path) -> None:
    sbom = {
        "spdxVersion": "SPDX-2.3",
        "dataLicense": "CC0-1.0",
        "SPDXID": "SPDXRef-DOCUMENT",
        "name": f"SkillShelf-{VERSION}",
        "packages": [
            {
                "name": "skillshelf",
                "SPDXID": "SPDXRef-Package-SkillShelf",
                "versionInfo": VERSION,
            }
        ],
    }
    (release / "SBOM.spdx.json").write_text(
        json.dumps(sbom, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    subjects = sorted(
        path
        for path in release.iterdir()
        if path.is_file()
        and path.name not in {"SHA256SUMS", "provenance-attestation.json"}
    )
    provenance = {
        "_type": "https://in-toto.io/Statement/v1",
        "subject": [
            {"name": path.name, "digest": {"sha256": _sha256(path)}}
            for path in subjects
        ],
        "predicateType": "https://slsa.dev/provenance/v1",
        "predicate": {
            "buildDefinition": {
                "buildType": "fixture",
                "externalParameters": {"version": VERSION},
                "resolvedDependencies": [],
            },
            "runDetails": {"builder": {"id": "test fixture"}},
        },
    }
    (release / "provenance-attestation.json").write_text(
        json.dumps(provenance, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    checksummed = sorted(
        path
        for path in release.iterdir()
        if path.is_file() and path.name != "SHA256SUMS"
    )
    (release / "SHA256SUMS").write_text(
        "".join(f"{_sha256(path)}  {path.name}\n" for path in checksummed),
        encoding="utf-8",
    )


@pytest.fixture
def release_fixture(tmp_path: Path) -> tuple[Path, Path]:
    repository = tmp_path / "repository"
    release = tmp_path / f"skillshelf-{VERSION}"
    repository.mkdir()
    release.mkdir()
    _write_repository(repository)

    plugin = release / f"skillshelf-plugin-{VERSION}.zip"
    wheel = release / WHEEL_NAME
    runtime = release / f"skillshelf-runtime-{VERSION}.zip"
    source = release / f"skillshelf-source-{VERSION}.zip"
    _write_plugin(plugin)
    _write_wheel(wheel)
    _write_sdist(release / SDIST_NAME)
    _write_zip(runtime, _runtime_entries(repository, wheel))
    _write_zip(source, {"VERSION": f"{VERSION}\n", "README.md": "# Source\n"})
    _refresh_metadata(release)
    return repository, release


def _validate(repository: Path, release: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            str(VALIDATOR),
            str(release),
            "--version",
            VERSION,
            "--repository-root",
            str(repository),
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


def test_accepts_complete_release_and_normalized_wheel_name(
    release_fixture: tuple[Path, Path],
) -> None:
    repository, release = release_fixture
    result = _validate(repository, release)
    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    assert report["version"] == VERSION
    assert WHEEL_NAME in report["artifacts"]
    assert len(report["artifacts"]) == 8


def test_rejects_checksum_mismatch(
    release_fixture: tuple[Path, Path],
) -> None:
    repository, release = release_fixture
    sums = release / "SHA256SUMS"
    lines = sums.read_text(encoding="utf-8").splitlines()
    lines[0] = f"{'0' * 64}  {lines[0].split('  ', 1)[1]}"
    sums.write_text("\n".join(lines) + "\n", encoding="utf-8")
    result = _validate(repository, release)
    assert result.returncode == 1
    assert "checksum mismatch" in result.stderr


def test_rejects_missing_runtime_member(
    release_fixture: tuple[Path, Path],
) -> None:
    repository, release = release_fixture
    wheel = release / WHEEL_NAME
    runtime = release / f"skillshelf-runtime-{VERSION}.zip"
    _write_zip(
        runtime,
        _runtime_entries(repository, wheel, omit="mcp/registry.yml"),
    )
    _refresh_metadata(release)
    result = _validate(repository, release)
    assert result.returncode == 1
    assert "runtime archive is missing required members" in result.stderr
    assert "mcp/registry.yml" in result.stderr


def test_rejects_version_inconsistent_plugin(
    release_fixture: tuple[Path, Path],
) -> None:
    repository, release = release_fixture
    _write_plugin(
        release / f"skillshelf-plugin-{VERSION}.zip",
        manifest_version="0.2.9",
    )
    _refresh_metadata(release)
    result = _validate(repository, release)
    assert result.returncode == 1
    assert "plugin manifest version is inconsistent" in result.stderr


def test_rejects_missing_required_artifact(
    release_fixture: tuple[Path, Path],
) -> None:
    repository, release = release_fixture
    (release / SDIST_NAME).unlink()
    _refresh_metadata(release)
    result = _validate(repository, release)
    assert result.returncode == 1
    assert "expected exactly one Python sdist" in result.stderr


def test_rejects_invalid_sdist_even_with_updated_integrity_documents(
    release_fixture: tuple[Path, Path],
) -> None:
    repository, release = release_fixture
    (release / SDIST_NAME).write_bytes(b"not a tar archive")
    _refresh_metadata(release)
    result = _validate(repository, release)
    assert result.returncode == 1
    assert "invalid sdist artifact" in result.stderr
