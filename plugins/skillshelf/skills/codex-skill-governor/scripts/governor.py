#!/usr/bin/env python3
"""Safe local state and staging operations for the Codex Skill Governor."""

from __future__ import annotations

import argparse
import datetime as dt
import difflib
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
from typing import Any, Iterator

SCHEMA_VERSION = 1
STATE_DIRS = (
    "observations",
    "principles",
    "reviews",
    "staged-updates",
    "backups",
    "evidence",
    "locks",
    "config",
)
OBSERVATION_TYPES = {
    "user-correction",
    "weak-trigger",
    "missing-coverage",
    "contradiction",
    "unused-complexity",
    "repeated-failure",
    "unsafe-mcp-expansion",
    "workflow-discovery",
}
SAFE_NAME = re.compile(r"^[a-z0-9][a-z0-9._-]{0,127}$")
REFERENCE = re.compile(
    r"(?<![A-Za-z0-9_.-])((?:references|scripts|assets)/[A-Za-z0-9_./-]+)"
)
SECRET_PATTERNS = (
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b"),
    re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"),
    re.compile(r"(?i)\b(?:password|passwd|api[_-]?key|access[_-]?token)\s*[:=]\s*\S+"),
)
BUILD_ARTIFACTS = re.compile(r"(^|/)(?:__pycache__|\.DS_Store)(?:/|$)|\.pyc$|(^|/)\.~lock\.")


class GovernorError(RuntimeError):
    """A validation or safety failure."""


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")


def resolve_state_root(explicit: str | None = None) -> Path:
    if explicit:
        root = Path(explicit).expanduser()
    else:
        codex_home = os.environ.get("CODEX_HOME")
        if codex_home:
            home = Path(codex_home).expanduser()
        elif os.name == "nt" and os.environ.get("USERPROFILE"):
            home = Path(os.environ["USERPROFILE"]) / ".codex"
        else:
            home = Path.home() / ".codex"
        root = home / "state" / "skillshelf-governor"
    return root.resolve(strict=False)


def ensure_contained(root: Path, candidate: Path) -> Path:
    root = root.resolve(strict=False)
    candidate = candidate.resolve(strict=False)
    if os.name == "nt":
        root_key = os.path.normcase(str(root)).removeprefix("\\\\?\\")
        candidate_key = os.path.normcase(str(candidate)).removeprefix("\\\\?\\")
        try:
            contained = os.path.commonpath((root_key, candidate_key)) == root_key
        except ValueError:
            contained = False
        if not contained:
            raise GovernorError(f"path escapes state root: {candidate}")
    else:
        try:
            candidate.relative_to(root)
        except ValueError as exc:
            raise GovernorError(f"path escapes state root: {candidate}") from exc
    return candidate


def init_state(root: Path) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    root = root.resolve()
    for name in STATE_DIRS:
        ensure_contained(root, root / name).mkdir(exist_ok=True)
    observations = root / "observations" / "observations.json"
    if not observations.exists():
        atomic_write_json(observations, {"schema_version": SCHEMA_VERSION, "observations": []})
    principles = root / "principles" / "principles.json"
    if not principles.exists():
        atomic_write_json(principles, {"schema_version": SCHEMA_VERSION, "principles": []})
    config = root / "config" / "config.json"
    if not config.exists():
        atomic_write_json(
            config,
            {
                "schema_version": SCHEMA_VERSION,
                "state_class": "skill-governance",
                "auto_modify_live_skills": False,
            },
        )
    return root


def atomic_write_bytes(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    temporary_path = Path(temporary)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        atomic_replace(temporary_path, path)
        if os.name != "nt":
            directory_fd = os.open(path.parent, os.O_RDONLY)
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
    finally:
        temporary_path.unlink(missing_ok=True)


def atomic_replace(source: Path, destination: Path, timeout: float = 3.0) -> None:
    """Replace with bounded retries for transient Windows sharing violations."""
    deadline = time.monotonic() + timeout
    while True:
        try:
            os.replace(source, destination)
            return
        except PermissionError:
            if time.monotonic() >= deadline:
                raise
            time.sleep(0.02)


def atomic_write_json(path: Path, value: Any) -> None:
    payload = (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8")
    atomic_write_bytes(path, payload)


def read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise GovernorError(f"cannot read valid JSON from {path}: {exc}") from exc


def validate_observation_store(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, dict) or value.get("schema_version") != SCHEMA_VERSION:
        raise GovernorError("invalid observation store schema")
    records = value.get("observations")
    if not isinstance(records, list):
        raise GovernorError("observations must be an array")
    seen: set[str] = set()
    required = {
        "id",
        "kind",
        "status",
        "created_at",
        "skill",
        "type",
        "issue",
        "suggested_improvement",
        "principle",
        "evidence",
    }
    for record in records:
        if not isinstance(record, dict) or not required.issubset(record):
            raise GovernorError("observation record is incomplete")
        if record["id"] in seen:
            raise GovernorError(f"duplicate observation id: {record['id']}")
        seen.add(record["id"])
        if record["kind"] != "skill-governance-observation":
            raise GovernorError("project memory is not valid governor state")
        if record["status"] not in {"OPEN", "ACTIONED", "DECLINED"}:
            raise GovernorError(f"invalid status for {record['id']}")
        if record["type"] not in OBSERVATION_TYPES:
            raise GovernorError(f"invalid type for {record['id']}")
        if not isinstance(record["evidence"], list) or not record["evidence"]:
            raise GovernorError(f"evidence is required for {record['id']}")
    return records


def validate_principle_store(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, dict) or value.get("schema_version") != SCHEMA_VERSION:
        raise GovernorError("invalid principle store schema")
    records = value.get("principles")
    if not isinstance(records, list):
        raise GovernorError("principles must be an array")
    seen: set[str] = set()
    for record in records:
        if not isinstance(record, dict):
            raise GovernorError("principle record must be an object")
        required = {"id", "kind", "status", "created_at", "title", "statement", "evidence"}
        if not required.issubset(record):
            raise GovernorError("principle record is incomplete")
        if record["id"] in seen:
            raise GovernorError(f"duplicate principle id: {record['id']}")
        seen.add(record["id"])
        if record["kind"] != "cross-cutting-skill-principle":
            raise GovernorError("invalid principle data class")
        if record["status"] not in {"ACTIVE", "RETIRED"}:
            raise GovernorError(f"invalid principle status: {record['id']}")
        if not isinstance(record["evidence"], list) or not record["evidence"]:
            raise GovernorError(f"evidence is required for {record['id']}")
    return records


def reject_secrets(values: list[str]) -> None:
    for value in values:
        if any(pattern.search(value) for pattern in SECRET_PATTERNS):
            raise GovernorError("potential secret detected; redact before governance logging")


def process_is_alive(pid: Any) -> bool:
    if not isinstance(pid, int) or pid <= 0:
        return False
    try:
        os.kill(pid, 0)
        return True
    except PermissionError:
        return True
    except OSError:
        return False


class FileLock:
    def __init__(
        self,
        root: Path,
        resource: str,
        timeout: float = 15.0,
        stale_after: float = 300.0,
        poll: float = 0.025,
    ) -> None:
        if not SAFE_NAME.fullmatch(resource):
            raise GovernorError(f"unsafe lock resource: {resource}")
        # Resolve the stable parent, not the contended leaf. On Windows,
        # resolving a lockfile while another writer unlinks it can briefly
        # produce an NTFS $Extend/$Deleted identity.
        lock_directory = ensure_contained(root, root / "locks")
        self.path = lock_directory / f"{resource}.lock"
        self.timeout = timeout
        self.stale_after = stale_after
        self.poll = poll
        self.token = uuid.uuid4().hex

    def acquire(self) -> None:
        deadline = time.monotonic() + self.timeout
        metadata = json.dumps(
            {
                "token": self.token,
                "pid": os.getpid(),
                "host": socket.gethostname(),
                "created_at": utc_now(),
            },
            sort_keys=True,
        ).encode("utf-8")
        while True:
            try:
                fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
                with os.fdopen(fd, "wb") as handle:
                    handle.write(metadata)
                    handle.flush()
                    os.fsync(handle.fileno())
                return
            except (FileExistsError, PermissionError) as exc:
                if isinstance(exc, PermissionError) and not self.path.exists():
                    if time.monotonic() >= deadline:
                        raise GovernorError(
                            f"permission denied acquiring lock: {self.path.name}"
                        ) from exc
                    time.sleep(self.poll)
                    continue
                try:
                    observed_stat = self.path.stat()
                    age = time.time() - observed_stat.st_mtime
                    if age > self.stale_after:
                        before = self.path.read_bytes()
                        try:
                            owner = json.loads(before.decode("utf-8"))
                        except (UnicodeDecodeError, json.JSONDecodeError):
                            owner = {}
                        if (
                            owner.get("host") == socket.gethostname()
                            and process_is_alive(owner.get("pid"))
                        ):
                            if time.monotonic() >= deadline:
                                raise GovernorError(
                                    f"active owner holds lock: {self.path.name}"
                                )
                            time.sleep(self.poll)
                            continue
                        current_stat = self.path.stat()
                        if (
                            current_stat.st_mtime_ns == observed_stat.st_mtime_ns
                            and self.path.read_bytes() == before
                        ):
                            self.path.unlink()
                            continue
                except FileNotFoundError:
                    continue
                if time.monotonic() >= deadline:
                    raise GovernorError(f"timed out acquiring lock: {self.path.name}")
                time.sleep(self.poll)

    def release(self) -> None:
        try:
            metadata = json.loads(self.path.read_text(encoding="utf-8"))
            if metadata.get("token") == self.token:
                self.path.unlink()
        except FileNotFoundError:
            return
        except (OSError, json.JSONDecodeError) as exc:
            raise GovernorError(f"cannot safely release owned lock {self.path}: {exc}") from exc

    def __enter__(self) -> "FileLock":
        self.acquire()
        return self

    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> None:
        self.release()


def backup_file(root: Path, source: Path, label: str) -> Path:
    if not SAFE_NAME.fullmatch(label):
        raise GovernorError(f"unsafe backup label: {label}")
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
    destination = ensure_contained(root, root / "backups" / f"{stamp}-{label}.json")
    shutil.copy2(source, destination)
    return destination


def add_observation(root: Path, record: dict[str, Any]) -> tuple[str, Path]:
    root = init_state(root)
    store_path = root / "observations" / "observations.json"
    with FileLock(root, "observations"):
        store = read_json(store_path)
        records = validate_observation_store(store)
        backup = backup_file(root, store_path, "observations")
        observation_id = record.get("id") or f"obs-{uuid.uuid4()}"
        candidate = {
            "id": observation_id,
            "kind": "skill-governance-observation",
            "status": "OPEN",
            "created_at": record.get("created_at") or utc_now(),
            "skill": str(record["skill"]).strip(),
            "type": str(record["type"]).strip(),
            "issue": str(record["issue"]).strip(),
            "suggested_improvement": str(record["suggested_improvement"]).strip(),
            "principle": str(record["principle"]).strip(),
            "evidence": list(record["evidence"]),
        }
        if not candidate["skill"] or candidate["type"] not in OBSERVATION_TYPES:
            raise GovernorError("skill and a valid observation type are required")
        if not all(candidate[field] for field in ("issue", "suggested_improvement", "principle")):
            raise GovernorError("issue, suggested improvement, and principle are required")
        if not candidate["evidence"]:
            raise GovernorError("at least one evidence reference is required")
        reject_secrets(
            [
                candidate["issue"],
                candidate["suggested_improvement"],
                candidate["principle"],
                *[str(value) for value in candidate["evidence"]],
            ]
        )
        if any(item.get("id") == observation_id for item in records):
            raise GovernorError(f"observation already exists: {observation_id}")
        new_store = {"schema_version": SCHEMA_VERSION, "observations": [*records, candidate]}
        atomic_write_json(store_path, new_store)
        verified = validate_observation_store(read_json(store_path))
        if sum(item["id"] == observation_id for item in verified) != 1:
            raise GovernorError(f"survival verification failed: {observation_id}")
        return observation_id, backup


def list_observations(root: Path, status: str | None = None) -> list[dict[str, Any]]:
    root = init_state(root)
    records = validate_observation_store(
        read_json(root / "observations" / "observations.json")
    )
    if status:
        records = [record for record in records if record["status"] == status]
    return records


def resolve_observation(
    root: Path, observation_id: str, status: str, resolution: str
) -> tuple[dict[str, Any], Path]:
    if status not in {"ACTIONED", "DECLINED"}:
        raise GovernorError("resolved status must be ACTIONED or DECLINED")
    if not resolution.strip():
        raise GovernorError("resolution evidence is required")
    reject_secrets([resolution])
    root = init_state(root)
    store_path = root / "observations" / "observations.json"
    with FileLock(root, "observations"):
        store = read_json(store_path)
        records = validate_observation_store(store)
        matches = [index for index, item in enumerate(records) if item["id"] == observation_id]
        if len(matches) != 1:
            raise GovernorError(f"observation must exist exactly once: {observation_id}")
        backup = backup_file(root, store_path, "observations")
        index = matches[0]
        updated = dict(records[index])
        updated.update(
            {
                "status": status,
                "resolved_at": utc_now(),
                "resolution": resolution.strip(),
            }
        )
        next_records = list(records)
        next_records[index] = updated
        atomic_write_json(
            store_path,
            {"schema_version": SCHEMA_VERSION, "observations": next_records},
        )
        verified = validate_observation_store(read_json(store_path))
        survivors = [item for item in verified if item["id"] == observation_id]
        if len(survivors) != 1 or survivors[0]["status"] != status:
            raise GovernorError(f"resolution survival verification failed: {observation_id}")
        return survivors[0], backup


def add_principle(
    root: Path, title: str, statement: str, evidence: list[str]
) -> tuple[str, Path]:
    if not title.strip() or not statement.strip() or not evidence:
        raise GovernorError("title, statement, and evidence are required")
    reject_secrets([title, statement, *evidence])
    root = init_state(root)
    store_path = root / "principles" / "principles.json"
    with FileLock(root, "principles"):
        store = read_json(store_path)
        records = validate_principle_store(store)
        backup = backup_file(root, store_path, "principles")
        identifier = f"principle-{uuid.uuid4()}"
        record = {
            "id": identifier,
            "kind": "cross-cutting-skill-principle",
            "status": "ACTIVE",
            "created_at": utc_now(),
            "title": title.strip(),
            "statement": statement.strip(),
            "evidence": list(evidence),
        }
        atomic_write_json(
            store_path,
            {"schema_version": SCHEMA_VERSION, "principles": [*records, record]},
        )
        verified = validate_principle_store(read_json(store_path))
        if sum(item["id"] == identifier for item in verified) != 1:
            raise GovernorError(f"principle survival verification failed: {identifier}")
        return identifier, backup


def list_principles(root: Path, status: str | None = None) -> list[dict[str, Any]]:
    root = init_state(root)
    records = validate_principle_store(
        read_json(root / "principles" / "principles.json")
    )
    if status:
        records = [record for record in records if record["status"] == status]
    return records


def is_link(path: Path) -> bool:
    if path.is_symlink():
        return True
    try:
        return bool(os.lstat(path).st_file_attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT)
    except (AttributeError, OSError):
        return False


def package_manifest(package: Path) -> dict[str, str]:
    package = package.resolve(strict=True)
    if not package.is_dir() or is_link(package):
        raise GovernorError(f"skill package must be a real directory: {package}")
    if not (package / "SKILL.md").is_file():
        raise GovernorError(f"skill package is missing SKILL.md: {package}")
    manifest: dict[str, str] = {}
    for path in sorted(package.rglob("*")):
        if is_link(path):
            raise GovernorError(f"links/reparse points are not allowed in packages: {path}")
        if path.is_file():
            relative = path.relative_to(package).as_posix()
            if BUILD_ARTIFACTS.search(relative):
                raise GovernorError(f"build artifact is not allowed in package: {relative}")
            manifest[relative] = hashlib.sha256(path.read_bytes()).hexdigest()
    return manifest


def aggregate_digest(manifest: dict[str, str]) -> str:
    digest = hashlib.sha256()
    for name, file_hash in sorted(manifest.items()):
        digest.update(f"{name}\0{file_hash}\n".encode("utf-8"))
    return digest.hexdigest()


def validate_references(package: Path, manifest: dict[str, str]) -> None:
    skill_text = (package / "SKILL.md").read_text(encoding="utf-8")
    missing = sorted(
        {
            match.group(1).rstrip(").,;:`")
            for match in REFERENCE.finditer(skill_text)
            if match.group(1).rstrip(").,;:`") not in manifest
        }
    )
    if missing:
        raise GovernorError(f"missing referenced package files: {', '.join(missing)}")


def copy_package_atomic(source: Path, destination: Path) -> None:
    temporary = destination.with_name(f".{destination.name}.{uuid.uuid4().hex}.tmp")
    try:
        shutil.copytree(source, temporary, copy_function=shutil.copy2)
        atomic_replace(temporary, destination)
    finally:
        if temporary.exists():
            shutil.rmtree(temporary)


def prepare_stage(root: Path, live_skill: Path, skill_name: str) -> dict[str, Any]:
    if not SAFE_NAME.fullmatch(skill_name):
        raise GovernorError(f"unsafe skill name: {skill_name}")
    root = init_state(root)
    live_skill = live_skill.resolve(strict=True)
    with FileLock(root, f"stage-{skill_name}"):
        live_before = package_manifest(live_skill)
        day = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d")
        stage_parent = ensure_contained(root, root / "staged-updates" / day)
        stage_parent.mkdir(parents=True, exist_ok=True)
        stage = ensure_contained(
            root, stage_parent / f"{skill_name}-{uuid.uuid4().hex[:12]}"
        )
        copy_package_atomic(live_skill, stage)
        staged = package_manifest(stage)
        live_after = package_manifest(live_skill)
        if staged != live_before:
            raise GovernorError("staged package does not match the fresh live package")
        if live_after != live_before:
            raise GovernorError("live package changed during staging")
        metadata = {
            "schema_version": SCHEMA_VERSION,
            "skill_name": skill_name,
            "created_at": utc_now(),
            "live_path": str(live_skill),
            "live_digest": aggregate_digest(live_before),
            "stage_path": str(stage),
            "stage_digest": aggregate_digest(staged),
            "status": "PREPARED_NOT_INSTALLED",
        }
        atomic_write_json(stage / ".governor-stage.json", metadata)
        return metadata


def verify_stage(root: Path, live_skill: Path, stage: Path) -> dict[str, Any]:
    root = init_state(root)
    live_skill = live_skill.resolve(strict=True)
    stage = ensure_contained(root, stage)
    if not stage.exists():
        raise GovernorError(f"stage does not exist: {stage}")
    metadata_path = stage / ".governor-stage.json"
    metadata = read_json(metadata_path)
    skill_name = metadata.get("skill_name")
    if not isinstance(skill_name, str) or not SAFE_NAME.fullmatch(skill_name):
        raise GovernorError("stage metadata has an invalid skill name")
    with FileLock(root, f"stage-{skill_name}"):
        live_manifest = package_manifest(live_skill)
        stage_manifest = package_manifest(stage)
        validate_references(stage, stage_manifest)
        live_digest = aggregate_digest(live_manifest)
        original_live_digest = metadata.get("live_digest")
        if live_digest != original_live_digest:
            raise GovernorError("live package changed since this stage was prepared; rebase")
        changed = sorted(
            name
            for name in set(live_manifest) | set(stage_manifest)
            if name != ".governor-stage.json"
            and live_manifest.get(name) != stage_manifest.get(name)
        )
        diff = "\n".join(
            difflib.unified_diff(
                (live_skill / "SKILL.md").read_text(encoding="utf-8").splitlines(),
                (stage / "SKILL.md").read_text(encoding="utf-8").splitlines(),
                fromfile="live/SKILL.md",
                tofile="staged/SKILL.md",
                lineterm="",
            )
        )
        report = {
            "schema_version": SCHEMA_VERSION,
            "skill_name": skill_name,
            "verified_at": utc_now(),
            "status": "VERIFIED_NOT_INSTALLED",
            "live_digest": live_digest,
            "stage_digest": aggregate_digest(
                {k: v for k, v in stage_manifest.items() if k != ".governor-stage.json"}
            ),
            "changed_files": changed,
            "skill_md_diff": diff,
            "live_unchanged": True,
            "references_complete": True,
        }
        report_name = (
            f"{dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ')}-"
            f"{skill_name}.json"
        )
        report_path = ensure_contained(root, root / "reviews" / report_name)
        atomic_write_json(report_path, report)
        report["report_path"] = str(report_path)
        return report


def doctor(root: Path) -> dict[str, Any]:
    root = init_state(root)
    records = validate_observation_store(
        read_json(root / "observations" / "observations.json")
    )
    principles = validate_principle_store(
        read_json(root / "principles" / "principles.json")
    )
    config = read_json(root / "config" / "config.json")
    if config.get("auto_modify_live_skills") is not False:
        raise GovernorError("auto_modify_live_skills must remain false")
    missing = [name for name in STATE_DIRS if not (root / name).is_dir()]
    if missing:
        raise GovernorError(f"state directories are missing: {', '.join(missing)}")
    probe = root / "config" / ".doctor-probe"
    atomic_write_bytes(probe, b"ok\n")
    probe.unlink()
    return {
        "state_root": str(root),
        "schema_version": SCHEMA_VERSION,
        "observations": len(records),
        "principles": len(principles),
        "directories": list(STATE_DIRS),
        "auto_modify_live_skills": False,
        "status": "ok",
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state-root", help="Override the governor state root")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("init")
    subparsers.add_parser("doctor")
    observe = subparsers.add_parser("observe")
    observe.add_argument("--skill", required=True)
    observe.add_argument("--type", choices=sorted(OBSERVATION_TYPES), required=True)
    observe.add_argument("--issue", required=True)
    observe.add_argument("--suggested-improvement", required=True)
    observe.add_argument("--principle", required=True)
    observe.add_argument("--evidence", action="append", required=True)
    listing = subparsers.add_parser("list")
    listing.add_argument("--status", choices=("OPEN", "ACTIONED", "DECLINED"))
    resolve = subparsers.add_parser("resolve")
    resolve.add_argument("--id", required=True)
    resolve.add_argument("--status", choices=("ACTIONED", "DECLINED"), required=True)
    resolve.add_argument("--resolution", required=True)
    principle = subparsers.add_parser("principle")
    principle.add_argument("--title", required=True)
    principle.add_argument("--statement", required=True)
    principle.add_argument("--evidence", action="append", required=True)
    principles = subparsers.add_parser("list-principles")
    principles.add_argument("--status", choices=("ACTIVE", "RETIRED"))
    prepare = subparsers.add_parser("prepare-stage")
    prepare.add_argument("--live-skill", required=True)
    prepare.add_argument("--skill-name", required=True)
    verify = subparsers.add_parser("verify-stage")
    verify.add_argument("--live-skill", required=True)
    verify.add_argument("--stage", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    root = resolve_state_root(args.state_root)
    try:
        if args.command == "init":
            output: Any = {"state_root": str(init_state(root)), "status": "initialized"}
        elif args.command == "doctor":
            output = doctor(root)
        elif args.command == "observe":
            observation_id, backup = add_observation(
                root,
                {
                    "skill": args.skill,
                    "type": args.type,
                    "issue": args.issue,
                    "suggested_improvement": args.suggested_improvement,
                    "principle": args.principle,
                    "evidence": args.evidence,
                },
            )
            output = {
                "observation_id": observation_id,
                "backup": str(backup),
                "survival_verified": True,
            }
        elif args.command == "list":
            output = list_observations(root, args.status)
        elif args.command == "resolve":
            record, backup = resolve_observation(
                root, args.id, args.status, args.resolution
            )
            output = {
                "observation": record,
                "backup": str(backup),
                "survival_verified": True,
            }
        elif args.command == "principle":
            principle_id, backup = add_principle(
                root, args.title, args.statement, args.evidence
            )
            output = {
                "principle_id": principle_id,
                "backup": str(backup),
                "survival_verified": True,
            }
        elif args.command == "list-principles":
            output = list_principles(root, args.status)
        elif args.command == "prepare-stage":
            output = prepare_stage(root, Path(args.live_skill), args.skill_name)
        elif args.command == "verify-stage":
            output = verify_stage(root, Path(args.live_skill), Path(args.stage))
        else:
            raise GovernorError(f"unsupported command: {args.command}")
        print(json.dumps(output, indent=2, sort_keys=True))
        return 0
    except GovernorError as exc:
        print(json.dumps({"status": "error", "error": str(exc)}, sort_keys=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
