from pathlib import Path

from ..skill_loader import SkillLoader


def discover_skills(root: Path) -> list[dict[str, str]]:
    return [item.__dict__ for item in SkillLoader(root).discover()]
