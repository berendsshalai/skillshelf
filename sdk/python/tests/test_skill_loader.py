import os
import time

import pytest

from skillshelf_agents.skill_loader import SkillLoader


def test_discovery_is_metadata_only(repo_root):
    loader = SkillLoader(repo_root)
    assert len(loader.discover()) == 5
    assert loader.loaded_paths() == ()


def test_valid_lazy_load_and_reference(repo_root):
    loader = SkillLoader(repo_root)
    skill = loader.load_skill("codex-memory")
    assert skill.id == "codex-memory"
    reference = loader.load_reference("codex-memory", "references/privacy.md")
    assert "privacy" in reference.content.casefold()
    assert len(loader.loaded_paths()) == 2


def test_missing_and_traversal_are_rejected(repo_root):
    loader = SkillLoader(repo_root)
    with pytest.raises(FileNotFoundError):
        loader.load_skill("missing")
    with pytest.raises(ValueError):
        loader.load_reference("codex-memory", "../../find-skills-codex/SKILL.md")


def test_malformed_duplicate_and_cache_invalidation(tmp_path):
    skills = tmp_path / "skills"
    for folder in ("one", "two"):
        path = skills / folder
        path.mkdir(parents=True)
        (path / "SKILL.md").write_text("---\nname: duplicate\ndescription: first\n---\nbody")
    with pytest.raises(ValueError, match="duplicate"):
        SkillLoader(tmp_path).discover()
    (skills / "two/SKILL.md").write_text("bad")
    with pytest.raises(ValueError, match="frontmatter"):
        SkillLoader(tmp_path).discover()
    (skills / "two/SKILL.md").write_text("---\nname: two\ndescription: second\n---\na")
    loader = SkillLoader(tmp_path)
    first = loader.load_skill("two")
    time.sleep(0.01)
    (skills / "two/SKILL.md").write_text("---\nname: two\ndescription: second\n---\nb")
    os.utime(skills / "two/SKILL.md", None)
    assert loader.load_skill("two").sha256 != first.sha256
