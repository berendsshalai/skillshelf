import pytest
from agents import RunContextWrapper

from skillshelf_agents.agent_factory import AgentFactory
from skillshelf_agents.config import Settings
from skillshelf_agents.orchestrator import SkillShelfOrchestrator
from skillshelf_agents.registry import RuntimeRegistry
from skillshelf_agents.skill_loader import SkillLoader
from skillshelf_agents.contracts import SpecialistResult


def test_factory_is_registry_driven_and_skills_stay_lazy(repo_root, tmp_path):
    registry = RuntimeRegistry.load(repo_root)
    loader = SkillLoader(repo_root)
    runtime = SkillShelfOrchestrator(registry, AgentFactory(registry, loader), Settings(home=tmp_path))
    assert set(runtime.specialists) == {item.id for item in registry.agents}
    assert loader.loaded_paths() == ()


@pytest.mark.asyncio
async def test_every_specialist_resolves_its_current_skill(repo_root, tmp_path):
    registry = RuntimeRegistry.load(repo_root)
    loader = SkillLoader(repo_root)
    runtime = SkillShelfOrchestrator(registry, AgentFactory(registry, loader), Settings(home=tmp_path))
    for definition in registry.agents:
        prompt = await runtime.specialists[definition.id].get_system_prompt(RunContextWrapper(context=None))
        assert definition.skill_path in definition.skill_path
        assert definition.skill in (prompt or "")
    assert len(loader.loaded_paths()) == 5


@pytest.mark.asyncio
async def test_model_run_fails_clearly_without_key(repo_root, tmp_path, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    registry = RuntimeRegistry.load(repo_root)
    runtime = SkillShelfOrchestrator(
        registry, AgentFactory(registry, SkillLoader(repo_root)), Settings(home=tmp_path)
    )
    with pytest.raises(RuntimeError, match="OPENAI_API_KEY"):
        await runtime.run("debug this failing test")


@pytest.mark.asyncio
async def test_async_run_succeeds_with_structured_sdk_result(repo_root, tmp_path, monkeypatch):
    class Details:
        cached_tokens = 3
        reasoning_tokens = 2

    class Usage:
        requests = 1
        input_tokens = 20
        output_tokens = 10
        total_tokens = 30
        input_tokens_details = Details()
        output_tokens_details = Details()

    class Result:
        final_output = SpecialistResult(
            agent_id="memory-agent",
            status="complete",
            summary="Prior decision found",
            context_for_master="Use the prior decision.",
        )
        context_wrapper = type("Context", (), {"usage": Usage()})()

    async def fake_run(*args, **kwargs):
        return Result()

    monkeypatch.setenv("OPENAI_API_KEY", "test-only-placeholder")
    monkeypatch.setattr("skillshelf_agents.orchestrator.Runner.run", fake_run)
    registry = RuntimeRegistry.load(repo_root)
    runtime = SkillShelfOrchestrator(
        registry, AgentFactory(registry, SkillLoader(repo_root)), Settings(home=tmp_path)
    )
    output = await runtime.run("what did we decide last week?", explicit_agent="memory-agent")
    assert output.answer == "Prior decision found"
    assert output.usage.total_tokens == 30
    assert runtime.sessions.list()
