#!/usr/bin/env python3
"""Validate a complete, internally consistent SkillShelf release directory."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import tarfile
import zipfile
from email.parser import Parser
from pathlib import Path, PurePosixPath
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
PROJECT_NAME = "skillshelf-agents"
SEMVER = re.compile(r"^\d+\.\d+\.\d+$")
SHA256 = re.compile(r"^[0-9a-f]{64}$")
CHECKSUM_LINE = re.compile(r"^([0-9a-f]{64})  ([^/\\]+)$")
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
RUNTIME_DIRECTORIES = (
    "agents/instructions",
    "agents/generated/codex",
    "mcp",
    "docs/agents",
    "docs/integrations",
)


class ReleaseValidationError(RuntimeError):
    """The release cannot be published safely."""


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def canonical_project_name(value: str) -> str:
    return re.sub(r"[-_.]+", "-", value).lower()


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ReleaseValidationError(f"invalid JSON artifact: {path.name}") from exc
    if not isinstance(value, dict):
        raise ReleaseValidationError(f"JSON object required: {path.name}")
    return value


def safe_archive_name(name: str, archive: Path) -> str:
    if "\\" in name:
        raise ReleaseValidationError(f"unsafe member in {archive.name}: {name}")
    member = PurePosixPath(name)
    if member.is_absolute() or ".." in member.parts:
        raise ReleaseValidationError(f"unsafe member in {archive.name}: {name}")
    return member.as_posix()


def inspect_zip(path: Path) -> tuple[zipfile.ZipFile, set[str]]:
    try:
        archive = zipfile.ZipFile(path)
        corrupt = archive.testzip()
    except (OSError, zipfile.BadZipFile) as exc:
        raise ReleaseValidationError(f"invalid ZIP artifact: {path.name}") from exc
    if corrupt is not None:
        archive.close()
        raise ReleaseValidationError(
            f"corrupt ZIP member in {path.name}: {corrupt}"
        )
    names = {safe_archive_name(name, path) for name in archive.namelist()}
    if len(names) != len(archive.namelist()):
        archive.close()
        raise ReleaseValidationError(f"duplicate ZIP member in {path.name}")
    return archive, names


def validate_plugin(path: Path, version: str) -> None:
    archive, names = inspect_zip(path)
    try:
        manifest_name = ".codex-plugin/plugin.json"
        if manifest_name not in names:
            raise ReleaseValidationError("plugin archive is missing its manifest")
        try:
            manifest = json.loads(archive.read(manifest_name))
        except (KeyError, json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise ReleaseValidationError("plugin manifest is invalid") from exc
        if not isinstance(manifest, dict) or manifest.get("version") != version:
            raise ReleaseValidationError("plugin manifest version is inconsistent")
        skills = {
            name
            for name in names
            if name.startswith("skills/")
            and name.endswith("/SKILL.md")
            and name.count("/") == 2
        }
        if len(skills) != 5:
            raise ReleaseValidationError(
                f"plugin archive must contain five skills; found {len(skills)}"
            )
    finally:
        archive.close()


def validate_wheel(path: Path, version: str) -> None:
    match = re.fullmatch(
        r"(?P<distribution>[A-Za-z0-9_.]+)-(?P<version>[^-]+)"
        r"-(?P<python>[^-]+)-(?P<abi>[^-]+)-(?P<platform>[^-]+)\.whl",
        path.name,
    )
    if match is None:
        raise ReleaseValidationError(f"invalid wheel filename: {path.name}")
    if canonical_project_name(match.group("distribution")) != PROJECT_NAME:
        raise ReleaseValidationError(f"wheel project name is inconsistent: {path.name}")
    if match.group("version") != version:
        raise ReleaseValidationError(f"wheel version is inconsistent: {path.name}")

    archive, names = inspect_zip(path)
    try:
        metadata_files = sorted(
            name for name in names if name.endswith(".dist-info/METADATA")
        )
        wheel_files = sorted(name for name in names if name.endswith(".dist-info/WHEEL"))
        record_files = sorted(
            name for name in names if name.endswith(".dist-info/RECORD")
        )
        if not (
            len(metadata_files) == len(wheel_files) == len(record_files) == 1
        ):
            raise ReleaseValidationError(
                f"wheel metadata structure is invalid: {path.name}"
            )
        dist_info = metadata_files[0].split("/", 1)[0]
        dist_info_suffix = f"-{version}.dist-info"
        if (
            not dist_info.endswith(dist_info_suffix)
            or canonical_project_name(dist_info[: -len(dist_info_suffix)])
            != PROJECT_NAME
        ):
            raise ReleaseValidationError(
                f"wheel dist-info directory is inconsistent: {dist_info}"
            )
        metadata = Parser().parsestr(
            archive.read(metadata_files[0]).decode("utf-8")
        )
        if canonical_project_name(metadata.get("Name", "")) != PROJECT_NAME:
            raise ReleaseValidationError("wheel METADATA project name is inconsistent")
        if metadata.get("Version") != version:
            raise ReleaseValidationError("wheel METADATA version is inconsistent")
        wheel_metadata = Parser().parsestr(
            archive.read(wheel_files[0]).decode("utf-8")
        )
        expected_tag = "-".join(
            (match.group("python"), match.group("abi"), match.group("platform"))
        )
        if (
            wheel_metadata.get("Wheel-Version") != "1.0"
            or expected_tag not in wheel_metadata.get_all("Tag", [])
        ):
            raise ReleaseValidationError("wheel tag metadata is inconsistent")
    except UnicodeDecodeError as exc:
        raise ReleaseValidationError("wheel METADATA is not UTF-8") from exc
    finally:
        archive.close()


def validate_sdist(path: Path, version: str) -> None:
    suffix = f"-{version}.tar.gz"
    if not path.name.endswith(suffix):
        raise ReleaseValidationError(f"sdist version is inconsistent: {path.name}")
    distribution = path.name[: -len(suffix)]
    if canonical_project_name(distribution) != PROJECT_NAME:
        raise ReleaseValidationError(f"sdist project name is inconsistent: {path.name}")
    try:
        with tarfile.open(path, mode="r:gz") as archive:
            members = archive.getmembers()
            if any(not (member.isfile() or member.isdir()) for member in members):
                raise ReleaseValidationError(
                    f"sdist contains unsupported member types: {path.name}"
                )
            names = {safe_archive_name(member.name, path) for member in members}
            if len(names) != len(members):
                raise ReleaseValidationError(
                    f"duplicate archive member in {path.name}"
                )
            roots = {PurePosixPath(name).parts[0] for name in names if name}
            if len(roots) != 1:
                raise ReleaseValidationError(
                    f"sdist must have one top-level directory: {path.name}"
                )
            root = next(iter(roots))
            root_suffix = f"-{version}"
            if (
                not root.endswith(root_suffix)
                or canonical_project_name(root[: -len(root_suffix)]) != PROJECT_NAME
            ):
                raise ReleaseValidationError(
                    f"sdist top-level directory is inconsistent: {root}"
                )
            metadata_name = f"{root}/PKG-INFO"
            if metadata_name not in names or f"{root}/pyproject.toml" not in names:
                raise ReleaseValidationError(
                    f"sdist metadata structure is invalid: {path.name}"
                )
            extracted = archive.extractfile(metadata_name)
            if extracted is None:
                raise ReleaseValidationError("sdist PKG-INFO is not a regular file")
            metadata = Parser().parsestr(extracted.read().decode("utf-8"))
    except (OSError, tarfile.TarError, UnicodeDecodeError) as exc:
        raise ReleaseValidationError(f"invalid sdist artifact: {path.name}") from exc
    if canonical_project_name(metadata.get("Name", "")) != PROJECT_NAME:
        raise ReleaseValidationError("sdist PKG-INFO project name is inconsistent")
    if metadata.get("Version") != version:
        raise ReleaseValidationError("sdist PKG-INFO version is inconsistent")


def required_runtime_members(repository_root: Path, wheel: Path) -> set[str]:
    required = set(RUNTIME_FILES)
    for relative in RUNTIME_FILES:
        if not (repository_root / relative).is_file():
            raise ReleaseValidationError(
                f"runtime source member is missing from repository: {relative}"
            )
    for relative in RUNTIME_DIRECTORIES:
        source = repository_root / relative
        if not source.is_dir():
            raise ReleaseValidationError(
                f"runtime source directory is missing: {relative}"
            )
        files = sorted(
            path
            for path in source.rglob("*")
            if path.is_file() and not path.is_symlink()
        )
        if not files:
            raise ReleaseValidationError(
                f"runtime source directory is empty: {relative}"
            )
        required.update(
            path.relative_to(repository_root).as_posix() for path in files
        )
    required.add(f"sdk/python/dist/{wheel.name}")
    return required


def validate_runtime(
    path: Path,
    version: str,
    wheel: Path,
    repository_root: Path,
) -> None:
    archive, names = inspect_zip(path)
    try:
        required = required_runtime_members(repository_root, wheel)
        missing = sorted(required - names)
        if missing:
            raise ReleaseValidationError(
                f"runtime archive is missing required members: {missing}"
            )
        try:
            bundled_version = archive.read("VERSION").decode("utf-8").strip()
        except (KeyError, UnicodeDecodeError) as exc:
            raise ReleaseValidationError("runtime VERSION is invalid") from exc
        if bundled_version != version:
            raise ReleaseValidationError("runtime VERSION is inconsistent")
        if archive.read(f"sdk/python/dist/{wheel.name}") != wheel.read_bytes():
            raise ReleaseValidationError(
                "runtime wheel differs from the release wheel"
            )
    finally:
        archive.close()


def validate_source(path: Path, version: str) -> None:
    archive, names = inspect_zip(path)
    try:
        if "VERSION" not in names:
            raise ReleaseValidationError("source archive is missing VERSION")
        try:
            bundled_version = archive.read("VERSION").decode("utf-8").strip()
        except (KeyError, UnicodeDecodeError) as exc:
            raise ReleaseValidationError("source VERSION is invalid") from exc
        if bundled_version != version:
            raise ReleaseValidationError("source VERSION is inconsistent")
    finally:
        archive.close()


def validate_sbom(path: Path, version: str) -> None:
    sbom = load_json(path)
    if sbom.get("spdxVersion") != "SPDX-2.3":
        raise ReleaseValidationError("SBOM does not declare SPDX-2.3")
    if sbom.get("SPDXID") != "SPDXRef-DOCUMENT":
        raise ReleaseValidationError("SBOM document identifier is invalid")
    packages = sbom.get("packages")
    if not isinstance(packages, list) or not packages:
        raise ReleaseValidationError("SBOM does not describe a package")
    matching = [
        package
        for package in packages
        if isinstance(package, dict)
        and str(package.get("name", "")).lower() == "skillshelf"
    ]
    if len(matching) != 1 or matching[0].get("versionInfo") != version:
        raise ReleaseValidationError("SBOM package version is inconsistent")


def validate_provenance(
    path: Path,
    version: str,
    expected_subjects: set[str],
    release_directory: Path,
) -> None:
    statement = load_json(path)
    if statement.get("_type") != "https://in-toto.io/Statement/v1":
        raise ReleaseValidationError("provenance statement type is invalid")
    if statement.get("predicateType") != "https://slsa.dev/provenance/v1":
        raise ReleaseValidationError("provenance predicate type is invalid")
    predicate = statement.get("predicate")
    if not isinstance(predicate, dict):
        raise ReleaseValidationError("provenance predicate is missing")
    build_definition = predicate.get("buildDefinition")
    if not isinstance(build_definition, dict):
        raise ReleaseValidationError("provenance build definition is missing")
    external = build_definition.get("externalParameters")
    if not isinstance(external, dict) or external.get("version") != version:
        raise ReleaseValidationError("provenance version is inconsistent")

    subjects = statement.get("subject")
    if not isinstance(subjects, list):
        raise ReleaseValidationError("provenance subjects are missing")
    observed: dict[str, str] = {}
    for subject in subjects:
        if not isinstance(subject, dict) or not isinstance(subject.get("name"), str):
            raise ReleaseValidationError("invalid provenance subject")
        name = str(subject["name"])
        digest = subject.get("digest")
        if (
            name in observed
            or "/" in name
            or "\\" in name
            or not isinstance(digest, dict)
            or not isinstance(digest.get("sha256"), str)
            or not SHA256.fullmatch(str(digest["sha256"]))
        ):
            raise ReleaseValidationError(f"invalid provenance subject: {name}")
        observed[name] = str(digest["sha256"])
    if set(observed) != expected_subjects:
        raise ReleaseValidationError(
            "provenance subject set does not match release artifacts"
        )
    for name, digest in observed.items():
        if sha256(release_directory / name) != digest:
            raise ReleaseValidationError(f"provenance digest mismatch: {name}")


def validate_checksums(path: Path, expected_files: set[str]) -> None:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise ReleaseValidationError("cannot read SHA256SUMS") from exc
    entries: dict[str, str] = {}
    for line in lines:
        match = CHECKSUM_LINE.fullmatch(line)
        if match is None or match.group(2) in entries:
            raise ReleaseValidationError(f"invalid SHA256SUMS entry: {line!r}")
        entries[match.group(2)] = match.group(1)
    if set(entries) != expected_files:
        raise ReleaseValidationError(
            "SHA256SUMS entries do not match release artifacts"
        )
    for name, digest in entries.items():
        if sha256(path.parent / name) != digest:
            raise ReleaseValidationError(f"checksum mismatch: {name}")


def validate_release(
    release_directory: Path,
    *,
    version: str,
    repository_root: Path = ROOT,
) -> list[str]:
    release_directory = release_directory.resolve(strict=True)
    repository_root = repository_root.resolve(strict=True)
    if not release_directory.is_dir():
        raise ReleaseValidationError("release path must be a directory")
    if not SEMVER.fullmatch(version):
        raise ReleaseValidationError(f"invalid release version: {version}")
    if release_directory.name != f"skillshelf-{version}":
        raise ReleaseValidationError("release directory version is inconsistent")

    expected_named = {
        f"skillshelf-plugin-{version}.zip",
        f"skillshelf-runtime-{version}.zip",
        f"skillshelf-source-{version}.zip",
        "SHA256SUMS",
        "SBOM.spdx.json",
        "provenance-attestation.json",
    }
    missing_named = sorted(
        name for name in expected_named if not (release_directory / name).is_file()
    )
    if missing_named:
        raise ReleaseValidationError(
            f"release directory is missing required artifacts: {missing_named}"
        )

    wheels = sorted(release_directory.glob("*.whl"))
    sdists = sorted(release_directory.glob("*.tar.gz"))
    if len(wheels) != 1:
        raise ReleaseValidationError(
            f"expected exactly one Python wheel; found {[path.name for path in wheels]}"
        )
    if len(sdists) != 1:
        raise ReleaseValidationError(
            f"expected exactly one Python sdist; found {[path.name for path in sdists]}"
        )
    wheel, sdist = wheels[0], sdists[0]
    plugin = release_directory / f"skillshelf-plugin-{version}.zip"
    runtime = release_directory / f"skillshelf-runtime-{version}.zip"
    source = release_directory / f"skillshelf-source-{version}.zip"
    sbom = release_directory / "SBOM.spdx.json"
    provenance = release_directory / "provenance-attestation.json"
    sums = release_directory / "SHA256SUMS"

    validate_plugin(plugin, version)
    validate_wheel(wheel, version)
    validate_sdist(sdist, version)
    validate_runtime(runtime, version, wheel, repository_root)
    validate_source(source, version)
    validate_sbom(sbom, version)

    release_files = {path.name for path in release_directory.iterdir() if path.is_file()}
    expected_release_files = expected_named | {wheel.name, sdist.name}
    if release_files != expected_release_files:
        raise ReleaseValidationError(
            f"release artifact set is inconsistent: {sorted(release_files)}"
        )
    validate_provenance(
        provenance,
        version,
        release_files - {"SHA256SUMS", provenance.name},
        release_directory,
    )
    validate_checksums(sums, release_files - {"SHA256SUMS"})
    return sorted(release_files)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "release_directory",
        nargs="?",
        type=Path,
        help="release directory (default: dist/skillshelf-<VERSION>)",
    )
    parser.add_argument("--version", help="expected semantic release version")
    parser.add_argument(
        "--repository-root",
        type=Path,
        default=ROOT,
        help=argparse.SUPPRESS,
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    version = args.version or (args.repository_root / "VERSION").read_text(
        encoding="utf-8"
    ).strip()
    release_directory = args.release_directory or (
        args.repository_root / "dist" / f"skillshelf-{version}"
    )
    try:
        artifacts = validate_release(
            release_directory,
            version=version,
            repository_root=args.repository_root,
        )
    except (OSError, ReleaseValidationError) as exc:
        print(f"release validation failed: {exc}", file=sys.stderr)
        return 1
    print(
        json.dumps(
            {
                "version": version,
                "directory": str(release_directory.resolve()),
                "artifacts": artifacts,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
