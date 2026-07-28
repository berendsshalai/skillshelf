import pytest
import yaml

from skillshelf_agents.registry import RuntimeRegistry


def test_registry_has_one_master_and_five_agents(repo_root):
    registry = RuntimeRegistry.load(repo_root)
    assert registry.master.id == "skillshelf-master"
    assert len(registry.agents) == 5
    assert len({item.skill for item in registry.agents}) == 5


def test_registry_rejects_unknown_mcp(repo_root, tmp_path):
    data = yaml.safe_load((repo_root / "agents/registry.yml").read_text())
    data["agents"][0]["allowed_mcp"].append("unrestricted-unknown")
    clone = tmp_path / "repo"
    clone.mkdir()
    for name in ("agents", "skills", "mcp"):
        (clone / name).symlink_to(repo_root / name, target_is_directory=True)
    (clone / "agents").unlink()
    (clone / "agents").mkdir()
    (clone / "agents/registry.yml").write_text(yaml.safe_dump(data))
    for name in ("model-profiles.yml", "instructions"):
        (clone / "agents" / name).symlink_to(
            repo_root / "agents" / name, target_is_directory=(name == "instructions")
        )
    with pytest.raises(ValueError, match="unknown MCP"):
        RuntimeRegistry.load(clone)
