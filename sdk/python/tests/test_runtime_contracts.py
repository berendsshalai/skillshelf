from __future__ import annotations

from pathlib import Path

import pytest
from agents import ModelSettings, RunContextWrapper

from skillshelf_agents.runtime.approvals import ApprovalStore, canonical_arguments_digest
from skillshelf_agents.runtime.budgets import BudgetLedger, BudgetLimitExceeded, RuntimeBudgetHooks
from skillshelf_agents.runtime.context import RuntimeContext
from skillshelf_agents.runtime.delegation import DelegationInput, build_delegation_prompt
from skillshelf_agents.runtime.results import (
    ArtifactReference,
    ExecutionEvidence,
    OperationalSpecialistResult,
    ToolExecutionEvidence,
    merge_mechanical_evidence,
)


def runtime_context(tmp_path: Path) -> RuntimeContext:
    return RuntimeContext(
        run_id="run-1",
        trace_id="trace-1",
        session_id="session-1",
        repository_root=tmp_path,
        repository_identity="github.com/example/repo",
        approval_grants=set(),
        soft_token_limit=100,
        hard_token_limit=120,
    )


def test_delegation_prompt_is_structured_bounded_and_omits_parent_history(tmp_path: Path) -> None:
    value = DelegationInput(
        task="Inspect the parser.",
        success_criteria=["Find the failing branch."],
        relevant_paths=["src/parser.py"],
        relevant_context=["The failure happens on empty input."],
        allowed_capabilities=["read_files"],
        prohibited_capabilities=["write_project_files"],
        input_token_budget=1200,
        output_token_budget=300,
        run_id="run-1",
        trace_id="trace-1",
    )

    prompt = build_delegation_prompt({"params": value.model_dump(mode="json")})

    assert "Inspect the parser." in prompt
    assert "src/parser.py" in prompt
    assert "read_files" in prompt
    assert "parent conversation" not in prompt.casefold()
    assert len(prompt) < 3000
    assert runtime_context(tmp_path).delegation_depth == 0


def test_mechanical_evidence_replaces_model_claims() -> None:
    model = OperationalSpecialistResult(
        agent_id="memory-agent",
        status="completed",
        summary="Found it.",
        context_for_master="Use the verified record.",
        artifacts=[
            ArtifactReference(
                artifact_id="invented",
                path="invented.txt",
                media_type="text/plain",
                sha256="0" * 64,
                size_bytes=1,
            )
        ],
        tool_executions=[],
    )
    mechanical = ExecutionEvidence(
        artifacts=[
            ArtifactReference(
                artifact_id="real",
                path="evidence/result.txt",
                media_type="text/plain",
                sha256="a" * 64,
                size_bytes=7,
            )
        ],
        tool_executions=[
            ToolExecutionEvidence(
                tool_call_id="call-1",
                tool_name="read_text_file",
                started_at="2026-07-28T00:00:00Z",
                completed_at="2026-07-28T00:00:01Z",
                status="completed",
                input_digest="b" * 64,
                output_digest="c" * 64,
            )
        ],
    )

    merged = merge_mechanical_evidence(model, mechanical)

    assert [item.artifact_id for item in merged.artifacts] == ["real"]
    assert [item.tool_call_id for item in merged.tool_executions] == ["call-1"]


def test_approval_is_bound_to_exact_arguments_and_expiry(tmp_path: Path) -> None:
    store = ApprovalStore(tmp_path / "runtime.sqlite")
    context = runtime_context(tmp_path)
    approval = store.request(
        context=context,
        tool_name="write_text_file",
        arguments={"path": "a.txt", "content": "one"},
        operation="replace",
        approving_user="sha-lai",
        ttl_seconds=60,
    )

    assert not store.is_granted(approval.approval_id)
    store.approve(approval.approval_id, approving_user="sha-lai")
    assert store.is_granted_for(
        approval.approval_id,
        context=context,
        tool_name="write_text_file",
        arguments={"content": "one", "path": "a.txt"},
        operation="replace",
    )
    assert not store.is_granted_for(
        approval.approval_id,
        context=context,
        tool_name="write_text_file",
        arguments={"path": "a.txt", "content": "two"},
        operation="replace",
    )
    assert canonical_arguments_digest({"b": 2, "a": 1}) == canonical_arguments_digest({"a": 1, "b": 2})


@pytest.mark.asyncio
async def test_budget_hook_blocks_the_next_request_and_preserves_request_usage(tmp_path: Path) -> None:
    context = runtime_context(tmp_path)
    ledger = BudgetLedger(context.soft_token_limit, context.hard_token_limit)
    ledger.record_request(
        agent_id="memory-agent",
        request_id="request-1",
        input_tokens=80,
        output_tokens=40,
        cached_tokens=5,
        reasoning_tokens=3,
    )
    hooks = RuntimeBudgetHooks(ledger)
    wrapper = RunContextWrapper(context=context)

    with pytest.raises(BudgetLimitExceeded):
        await hooks.on_llm_start(wrapper, object(), None, [])

    assert ledger.run_total.total_tokens == 120
    assert ledger.by_agent["memory-agent"].total_tokens == 120
    assert ledger.by_request[0].request_id == "request-1"
    assert not ledger.optional_calls_allowed
    assert ModelSettings(max_tokens=300).max_tokens == 300
