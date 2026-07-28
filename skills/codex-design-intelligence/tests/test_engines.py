import pathlib

ROOT = pathlib.Path(__file__).parents[3]

def test_engines_are_separate():
    assert (ROOT / "vendor/impeccable/impeccable/SKILL.md").is_file()
    assert (ROOT / "vendor/taste-skill/skills/taste-skill/SKILL.md").is_file()
    matrix = (ROOT / "skills/codex-design-intelligence/references/design-authority-matrix.md").read_text()
    assert "Accessibility" in matrix and "Impeccable" in matrix and "Taste" in matrix
