import pytest

from skillshelf_agents.mcp_runtime import MCPRuntime
from skillshelf_agents.registry import RuntimeRegistry


def test_only_assigned_mcp_and_writes_need_approval(repo_root):
    runtime = MCPRuntime(repo_root)
    registry = RuntimeRegistry.load(repo_root)
    memory = registry.by_id("memory-agent")
    assert set(runtime.permissions(memory.allowed_mcp)) == {"skillshelf-memory"}
    with pytest.raises(PermissionError):
        runtime.tools("github-project", include_writes=True)
    assert "branch_push" in runtime.tools("github-project", include_writes=True, approved=True)
