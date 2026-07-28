import json, pathlib, re, tomllib

ROOT = pathlib.Path(__file__).parents[1]
EXPECTED = {"find-skills-codex", "superpowers-codex", "codex-memory", "codex-design-intelligence", "codex-skill-governor"}

def test_exactly_five_skills():
    assert {p.name for p in (ROOT / "skills").iterdir() if p.is_dir()} == EXPECTED

def test_plugin_manifest():
    manifest = json.loads((ROOT / ".codex-plugin/plugin.json").read_text())
    assert manifest["name"] == "skillshelf"
    assert manifest["skills"] == "./skills/"
    assert "mcpServers" not in manifest
    assert len(manifest["interface"]["defaultPrompt"]) <= 128
    marketplace = json.loads((ROOT / ".agents/plugins/marketplace.json").read_text())
    assert marketplace["plugins"][0]["source"]["path"] == "./plugins/skillshelf"

def test_agents_parse_and_declare_boundaries():
    files = list((ROOT / ".codex/agents").glob("*.toml"))
    assert len(files) == 8
    for path in files:
        data = tomllib.loads(path.read_text())
        assert {"name", "description", "developer_instructions"} <= data.keys()
        assert "Use " in data["developer_instructions"]
        if data["sandbox_mode"] == "read-only":
            assert re.search(r"no write|Never call write|no write tool|Reject undeclared write", data["developer_instructions"], re.I)

def test_required_documents():
    for name in ("README.md", "ARCHITECTURE.md", "MASTER_BUILD_PROMPT.md", "HANDOFF.md",
                 "CONTRIBUTING.md", "SECURITY.md", "CHANGELOG.md", "ROADMAP.md", "THIRD_PARTY_NOTICES.md"):
        assert (ROOT / name).is_file()
