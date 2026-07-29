from __future__ import annotations

from agents import Agent, Runner, function_tool

from skillshelf_agents.contracts import OrchestratorResult, SpecialistResult
from skillshelf_agents.runtime.delegation import DelegationInput, build_delegation_prompt
from skillshelf_agents.runtime.scripted_model import ScriptedModel, ScriptedModelStep


def test_actual_agent_graph_delegates_and_executes_function_tool() -> None:
    calls: list[str] = []

    def inspect_file(path: str) -> dict[str, str]:
        """Inspect one deterministic repository file."""
        calls.append(path)
        return {"path": path, "sha256": "a" * 64}

    specialist_model = ScriptedModel(
        [
            ScriptedModelStep.tool_call("inspect_file", {"path": "README.md"}),
            ScriptedModelStep.structured_output(
                SpecialistResult(
                    agent_id="superpowers-agent",
                    status="completed",
                    summary="Inspected the requested file.",
                    context_for_master="README.md was inspected by a real function tool.",
                ).model_dump(mode="json")
            ),
        ]
    )
    specialist = Agent(
        name="Superpowers Agent",
        instructions="Use the function tool and return SpecialistResult.",
        model=specialist_model,
        tools=[function_tool(inspect_file)],
        output_type=SpecialistResult,
    )
    delegation = DelegationInput(
        task="Inspect README.md",
        success_criteria=["Return a digest."],
        relevant_paths=["README.md"],
        allowed_capabilities=["read_files"],
        prohibited_capabilities=["write_project_files"],
        input_token_budget=500,
        output_token_budget=200,
        run_id="run-1",
        trace_id="trace-1",
    )
    master_model = ScriptedModel(
        [
            ScriptedModelStep.tool_call(
                "software_methodology_specialist", delegation.model_dump(mode="json")
            ),
            ScriptedModelStep.structured_output(
                OrchestratorResult(
                    status="completed",
                    answer="The specialist inspected README.md.",
                    specialists_used=["superpowers-agent"],
                ).model_dump(mode="json")
            ),
        ]
    )
    master = Agent(
        name="SkillShelf Master",
        instructions="Delegate once and reconcile the structured result.",
        model=master_model,
        tools=[
            specialist.as_tool(
                "software_methodology_specialist",
                "Inspect and verify software artifacts.",
                parameters=DelegationInput,
                input_builder=build_delegation_prompt,
                include_input_schema=True,
            )
        ],
        output_type=OrchestratorResult,
    )

    result = Runner.run_sync(master, "Inspect README.md")

    assert result.final_output.answer == "The specialist inspected README.md."
    assert calls == ["README.md"]
    assert len(master_model.requests) == 2
    assert len(specialist_model.requests) == 2
    assert specialist_model.requests[0]["max_tokens"] is None
