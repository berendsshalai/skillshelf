from __future__ import annotations

import inspect

import pytest
import yaml

from skillshelf_agents.mcp_runtime import MCPRuntime
from skillshelf_agents.registry import RuntimeRegistry


def test_only_assigned_mcp_and_approval_cannot_be_forged_with_boolean(repo_root):
    runtime = MCPRuntime(repo_root)
    registry = RuntimeRegistry.load(repo_root)
    memory = registry.by_id("memory-agent")

    assert set(runtime.permissions(memory.allowed_mcp)) == {"skillshelf-memory"}
    with pytest.raises(PermissionError, match="durable approval"):
        runtime.tools("github-project", include_writes=True)
    assert "approved" not in inspect.signature(runtime.tools).parameters
    with pytest.raises(TypeError):
        runtime.tools("github-project", include_writes=True, approved=True)  # type: ignore[call-arg]


def test_manifest_has_real_sdk_transports_but_host_adapters_stay_external(repo_root):
    runtime = MCPRuntime(repo_root)
    memory = runtime.servers["skillshelf-memory"]
    docs = runtime.servers["openaiDeveloperDocs"]
    filesystem = runtime.servers["filesystem"]
    github = runtime.servers["github"]

    assert memory.operational is not None
    assert memory.operational.command == "node"
    assert memory.operational.args[-1].endswith("mcp-server.cjs")
    assert (repo_root / memory.operational.args[-1]).is_file()
    assert docs.operational is not None
    assert docs.operational.url == "https://developers.openai.com/mcp"
    assert filesystem.operational is None
    assert filesystem.adapter == "host-provided"
    assert github.operational is None
    assert github.adapter == "host-provided"
    assert len(runtime.manager.servers) == 3


def test_manifest_references_secrets_without_embedding_values(repo_root):
    raw = yaml.safe_load((repo_root / "mcp" / "registry.yml").read_text(encoding="utf-8"))
    github = next(item for item in raw["servers"] if item["name"] == "github")

    assert github["secret_references"] == [{"environment": "GH_TOKEN"}]
    assert "secret_values" not in github
    assert "token" not in github


def test_health_never_passes_optional_unconnected_services(repo_root):
    runtime = MCPRuntime(repo_root)
    health = runtime.health()

    assert health["skillshelf-memory"] in {"SKIPPED", "DEGRADED"}
    assert health["openaiDeveloperDocs"] in {"SKIPPED", "DEGRADED"}
    assert health["github"] in {"SKIPPED", "DEGRADED"}
    assert health["filesystem"] == "PASS"
