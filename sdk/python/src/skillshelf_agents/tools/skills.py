from __future__ import annotations

from pathlib import Path

from ..skill_loader import SkillLoader


def discover_skill_metadata(repository_root: Path) -> list[dict[str, str]]:
    return [item.__dict__ for item in SkillLoader(repository_root).discover()]
