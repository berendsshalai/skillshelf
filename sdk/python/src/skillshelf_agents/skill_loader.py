from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path

import yaml

FRONTMATTER = re.compile(r"\A---\r?\n(.*?)\r?\n---\r?\n", re.DOTALL)


@dataclass(frozen=True)
class SkillSummary:
    id: str
    description: str
    path: str


@dataclass(frozen=True)
class LoadedSkill:
    id: str
    description: str
    content: str
    path: str
    sha256: str


@dataclass(frozen=True)
class LoadedReference:
    skill_id: str
    relative_path: str
    content: str
    sha256: str


class SkillLoader:
    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        self.skills_root = (self.root / "skills").resolve()
        self._cache: dict[Path, tuple[int, int, str, str]] = {}
        self._loaded: list[str] = []

    def _safe(self, path: Path, base: Path) -> Path:
        resolved = path.resolve()
        if resolved != base and base not in resolved.parents:
            raise ValueError("path traversal or cross-skill access denied")
        return resolved

    def _read(self, path: Path) -> tuple[str, str]:
        stat = path.stat()
        cached = self._cache.get(path)
        raw = path.read_bytes()
        digest = hashlib.sha256(raw).hexdigest()
        if cached and cached[:3] == (stat.st_mtime_ns, stat.st_size, digest):
            text = cached[3]
        else:
            text = raw.decode("utf-8")
            self._cache[path] = (stat.st_mtime_ns, stat.st_size, digest, text)
        value = path.relative_to(self.root).as_posix()
        if value not in self._loaded:
            self._loaded.append(value)
        return text, digest

    def _metadata(self, path: Path) -> dict[str, str]:
        text = path.read_text(encoding="utf-8")
        match = FRONTMATTER.match(text)
        if not match:
            raise ValueError(f"malformed frontmatter: {path}")
        data = yaml.safe_load(match.group(1))
        if not isinstance(data, dict) or not data.get("name") or not data.get("description"):
            raise ValueError(f"incomplete frontmatter: {path}")
        return data

    def discover(self) -> list[SkillSummary]:
        summaries: list[SkillSummary] = []
        names: set[str] = set()
        for path in sorted(self.skills_root.glob("*/SKILL.md")):
            data = self._metadata(path)
            if data["name"] in names:
                raise ValueError(f"duplicate skill name: {data['name']}")
            names.add(data["name"])
            summaries.append(
                SkillSummary(data["name"], data["description"], path.relative_to(self.root).as_posix())
            )
        return summaries

    def load_skill(self, skill_id: str) -> LoadedSkill:
        path = self._safe(self.skills_root / skill_id / "SKILL.md", self.skills_root)
        if not path.is_file():
            raise FileNotFoundError(skill_id)
        metadata = self._metadata(path)
        if metadata["name"] != skill_id:
            raise ValueError("skill directory and frontmatter name differ")
        content, digest = self._read(path)
        return LoadedSkill(
            skill_id, metadata["description"], content, path.relative_to(self.root).as_posix(), digest
        )

    def load_reference(self, skill_id: str, relative_path: str) -> LoadedReference:
        base = self._safe(self.skills_root / skill_id, self.skills_root)
        path = self._safe(base / relative_path, base)
        if not path.is_file() or path.name == "SKILL.md":
            raise FileNotFoundError(relative_path)
        content, digest = self._read(path)
        return LoadedReference(skill_id, relative_path, content, digest)

    def loaded_paths(self) -> tuple[str, ...]:
        return tuple(self._loaded)
