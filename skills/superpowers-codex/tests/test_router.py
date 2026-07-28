import pathlib, re

ROOT = pathlib.Path(__file__).parents[3]

def test_required_modules_exist():
    text = (ROOT / "skills/superpowers-codex/SEMANTIC_CONTRACT.yml").read_text()
    modules = re.findall(r"^  - ([a-z][a-z0-9-]+)$", text, re.MULTILINE)
    for module in modules[:13]:
        assert (ROOT / "vendor/superpowers/skills" / module / "SKILL.md").is_file()
