import pathlib

ROOT = pathlib.Path(__file__).parents[1]

def text(skill):
    return (ROOT / "skills" / skill / "SKILL.md").read_text()

def test_find_skills_refuses_blind_install():
    value = text("find-skills-codex")
    assert "Never judge or install from a search-result title alone" in value
    assert "immutable commit" in value

def test_superpowers_feature_route():
    value = text("superpowers-codex")
    assert "`brainstorming` -> `writing-plans` -> implementation" in value
    assert "`systematic-debugging` -> `test-driven-development` -> verification" in value

def test_memory_progressive_retrieval():
    value = text("codex-memory")
    for phrase in ("call `search`", "call `timeline`", "batch `get_observations`"):
        assert phrase in value
    assert "Never inject the database" in value

def test_design_operate_and_bounded_review():
    value = text("codex-design-intelligence")
    assert "**Operate**" in value
    assert "one bounded consolidated review" in value

def test_governor_stages_only():
    value = text("codex-skill-governor")
    assert "Never modify live skills automatically" in value
    assert "staged" in value.lower()
