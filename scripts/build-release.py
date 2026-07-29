#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
import sys
import zipfile
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERSION = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
DIST = ROOT / "dist" / f"skillshelf-{VERSION}"
EXCLUDED_PARTS = {".git", ".venv", "__pycache__", "dist", "work", "upstream"}
LOCK_PATHS = (
    Path("sdk/python/requirements.lock"),
    Path("sdk/python/requirements.lock.sha256"),
    Path("upstream-lock.json"),
    Path("vendor-manifest.json"),
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def allowed(path: Path) -> bool:
    relative = path.relative_to(ROOT)
    return not EXCLUDED_PARTS.intersection(relative.parts) and not path.is_symlink()


def zip_paths(destination: Path, paths: list[Path]) -> None:
    with zipfile.ZipFile(destination, "w", zipfile.ZIP_DEFLATED) as archive:
        for source in paths:
            candidates = [source] if source.is_file() else sorted(source.rglob("*"))
            for path in candidates:
                if not path.is_file():
                    continue
                if path.is_relative_to(DIST):
                    archive.write(path, f"sdk/python/dist/{path.name}")
                elif allowed(path):
                    archive.write(path, path.relative_to(ROOT).as_posix())


def run(command: list[str]) -> None:
    subprocess.run(command, cwd=ROOT, check=True)


def spdx_id(value: str) -> str:
    return "SPDXRef-" + re.sub(r"[^A-Za-z0-9.-]+", "-", value).strip("-")


def locked_python_packages() -> list[dict[str, object]]:
    packages: list[dict[str, object]] = []
    pattern = re.compile(r"^([A-Za-z0-9_.-]+)==([^;\s]+)")
    for line in (
        (ROOT / "sdk/python/requirements.lock").read_text(encoding="utf-8").splitlines()
    ):
        match = pattern.match(line)
        if not match:
            continue
        name, version = match.groups()
        packages.append(
            {
                "name": name,
                "SPDXID": spdx_id(f"Python-{name}-{version}"),
                "versionInfo": version,
                "downloadLocation": "NOASSERTION",
                "filesAnalyzed": False,
                "licenseConcluded": "NOASSERTION",
                "externalRefs": [
                    {
                        "referenceCategory": "PACKAGE-MANAGER",
                        "referenceType": "purl",
                        "referenceLocator": f"pkg:pypi/{name.lower()}@{version}",
                    }
                ],
            }
        )
    return packages


def pinned_upstream_packages() -> list[dict[str, object]]:
    lock = json.loads((ROOT / "upstream-lock.json").read_text(encoding="utf-8"))
    packages: list[dict[str, object]] = []
    for index, source in enumerate(lock["sources"], start=1):
        repository = str(source["repository"])
        name = repository.rstrip("/").rsplit("/", 1)[-1]
        commit = str(source["commit"])
        packages.append(
            {
                "name": name,
                "SPDXID": spdx_id(f"Upstream-{index}-{name}"),
                "versionInfo": commit,
                "downloadLocation": repository,
                "filesAnalyzed": False,
                "licenseConcluded": str(source["license"]),
                "supplier": "NOASSERTION",
            }
        )
    return packages


def git_build_state() -> dict[str, object]:
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    dirty = bool(
        subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
    )
    return {"commit": commit, "dirty": dirty}


def main() -> int:
    run([sys.executable, str(ROOT / "scripts" / "validate-version.py")])
    if DIST.exists():
        shutil.rmtree(DIST)
    DIST.mkdir(parents=True)

    run([sys.executable, str(ROOT / "scripts" / "build-plugin.py")])
    plugin_source = ROOT / "dist" / f"skillshelf-{VERSION}.zip"
    plugin_target = DIST / f"skillshelf-plugin-{VERSION}.zip"
    shutil.copy2(plugin_source, plugin_target)

    run(
        [
            sys.executable,
            "-m",
            "build",
            str(ROOT / "sdk" / "python"),
            "--outdir",
            str(DIST),
        ]
    )
    wheel = DIST / f"skillshelf_agents-{VERSION}-py3-none-any.whl"
    if not wheel.is_file():
        raise FileNotFoundError(wheel)

    runtime = DIST / f"skillshelf-runtime-{VERSION}.zip"
    runtime_paths = [
        ROOT / "agents" / "registry.yml",
        ROOT / "agents" / "registry.schema.json",
        ROOT / "agents" / "instructions",
        ROOT / "agents" / "generated" / "codex",
        ROOT / "mcp",
        wheel,
        ROOT / "scripts" / "install-agent-runtime.ps1",
        ROOT / "scripts" / "install-agent-runtime.sh",
        ROOT / "scripts" / "uninstall-agent-runtime.ps1",
        ROOT / "scripts" / "uninstall-agent-runtime.sh",
        ROOT / "docs" / "agents",
        ROOT / "docs" / "integrations",
        ROOT / "docs" / "security",
        ROOT / "LICENSE",
        ROOT / "THIRD_PARTY_NOTICES.md",
        ROOT / "VERSION",
    ]
    zip_paths(runtime, [path for path in runtime_paths if path.exists()])

    source = DIST / f"skillshelf-source-{VERSION}.zip"
    zip_paths(source, [path for path in ROOT.iterdir() if allowed(path)])

    artifact_files = sorted(
        path
        for path in DIST.iterdir()
        if path.is_file() and path.name not in {"SHA256SUMS", "SBOM.spdx.json"}
    )
    root_package = {
        "name": "skillshelf",
        "SPDXID": "SPDXRef-Package-SkillShelf",
        "versionInfo": VERSION,
        "downloadLocation": "NOASSERTION",
        "filesAnalyzed": False,
        "licenseConcluded": "MIT",
    }
    dependency_packages = locked_python_packages() + pinned_upstream_packages()
    sbom = {
        "spdxVersion": "SPDX-2.3",
        "dataLicense": "CC0-1.0",
        "SPDXID": "SPDXRef-DOCUMENT",
        "name": f"SkillShelf-{VERSION}",
        "documentNamespace": f"https://github.com/berendsshalai/skillshelf/releases/v{VERSION}/sbom",
        "creationInfo": {
            "created": datetime.now(UTC).isoformat(),
            "creators": ["Tool: SkillShelf build-release.py"],
        },
        "packages": [root_package, *dependency_packages],
        "relationships": [
            {
                "spdxElementId": "SPDXRef-DOCUMENT",
                "relationshipType": "DESCRIBES",
                "relatedSpdxElement": "SPDXRef-Package-SkillShelf",
            },
            *[
                {
                    "spdxElementId": "SPDXRef-Package-SkillShelf",
                    "relationshipType": "DEPENDS_ON",
                    "relatedSpdxElement": package["SPDXID"],
                }
                for package in dependency_packages
            ],
        ],
    }
    (DIST / "SBOM.spdx.json").write_text(
        json.dumps(sbom, indent=2) + "\n", encoding="utf-8"
    )
    artifact_files.append(DIST / "SBOM.spdx.json")
    dependency_locks = [
        {
            "uri": path.as_posix(),
            "digest": {"sha256": sha256(ROOT / path)},
        }
        for path in LOCK_PATHS
    ]
    provenance = {
        "_type": "https://in-toto.io/Statement/v1",
        "subject": [
            {"name": path.name, "digest": {"sha256": sha256(path)}}
            for path in artifact_files
        ],
        "predicateType": "https://slsa.dev/provenance/v1",
        "predicate": {
            "buildDefinition": {
                "buildType": "https://github.com/berendsshalai/skillshelf/build-release/v1",
                "externalParameters": {
                    "version": VERSION,
                    "source": git_build_state(),
                    "python": sys.version.split()[0],
                },
                "resolvedDependencies": dependency_locks,
            },
            "runDetails": {
                "builder": {"id": "scripts/build-release.py"},
                "metadata": {"invocationId": datetime.now(UTC).isoformat()},
            },
        },
    }
    provenance_path = DIST / "provenance-attestation.json"
    provenance_path.write_text(
        json.dumps(provenance, indent=2) + "\n", encoding="utf-8"
    )
    artifact_files.append(provenance_path)
    sums = (
        "\n".join(f"{sha256(path)}  {path.name}" for path in sorted(artifact_files))
        + "\n"
    )
    (DIST / "SHA256SUMS").write_text(sums, encoding="utf-8")
    run(
        [
            sys.executable,
            str(ROOT / "scripts" / "validate-release.py"),
            str(DIST),
            "--version",
            VERSION,
        ]
    )
    print(
        json.dumps(
            {
                "version": VERSION,
                "directory": str(DIST),
                "artifacts": sorted(p.name for p in DIST.iterdir()),
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
