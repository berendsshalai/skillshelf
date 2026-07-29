from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from skillshelf_agents.event_log import EventLog
from skillshelf_agents.mcp.assignment import (
    MCPAssignment,
    MCPAssignmentResolver,
    MCPRequiredServerUnavailable,
)
from skillshelf_agents.mcp.contracts import MCPServerDefinition
from skillshelf_agents.mcp.factory import MCPFactory
from skillshelf_agents.registry import AgentDefinition
from skillshelf_agents.runtime.approvals import ApprovalStore, RunCheckpointStore
from skillshelf_agents.runtime.budgets import (
    BudgetLedger,
    BudgetLimitExceeded,
    BudgetScope,
)
from skillshelf_agents.runtime.capabilities import (
    AgentCapabilityUnavailable,
    CapabilityProviderType,
    CapabilityResolver,
)
from skillshelf_agents.runtime.context import RuntimeContext
from skillshelf_agents.runtime.evidence import RunEvidenceRecorder, execute_recorded


def definition(**updates: Any) -> AgentDefinition:
    data = {
        "id": "test-agent",
        "display_name": "Test Agent",
        "skill": "test-skill",
        "skill_path": "skills/test/SKILL.md",
        "instruction_file": "agents/test.md",
        "model_profile": "test",
        "output_contract": "SpecialistResult",
        "max_turns": 3,
        "tool_name": "test_specialist",
        "tool_description": "Test",
        "allowed_mcp": ["optional-server"],
        "allowed_capabilities": [
            {
                "id": "read_files",
                "required": True,
                "providers": ["read_files"],
                "degraded_behavior": "fail",
            }
        ],
        "prohibited_capabilities": ["write"],
        "token_budget": {"input": 100, "output": 50},
    }
    data.update(updates)
    return AgentDefinition.model_validate(data)


def context(tmp_path: Path) -> RuntimeContext:
    return RuntimeContext(
        run_id="run-1",
        trace_id="trace-1",
        session_id="session-1",
        repository_root=tmp_path,
        repository_identity="example/repo",
        soft_token_limit=100,
        hard_token_limit=120,
    )


class FakeFunctionRegistry:
    def supports(self, capability: str) -> bool:
        return capability == "read_files"

    def build(self, capabilities: list[str]) -> list[Any]:
        return [SimpleNamespace(name=f"{capabilities[0]}_tool")]


def test_structured_capability_migration_and_strict_resolution() -> None:
    item = definition()
    assert item.allowed_capabilities == ["read_files"]
    assert item.capability_policies[0].providers == ["read_files"]
    report = CapabilityResolver(FakeFunctionRegistry()).resolve(item)
    assert report.resolutions[0].provider_type == CapabilityProviderType.FUNCTION_TOOL

    missing = definition(
        allowed_capabilities=[
            {
                "id": "inspect_browser",
                "required": True,
                "providers": ["host-browser"],
                "degraded_behavior": "fail",
            }
        ]
    )
    with pytest.raises(AgentCapabilityUnavailable, match="skillshelf doctor --deep"):
        CapabilityResolver(FakeFunctionRegistry()).resolve(missing, mcp_assignment=MCPAssignment())


class FakeMCPDefinition:
    def __init__(self, name: str, *, required: bool, host: bool = False) -> None:
        self.name = name
        self.adapter = "host-provided" if host else None
        self._required = required

    def required_for(self, _agent_id: str) -> bool:
        return self._required


class FakeMCPRuntime:
    def __init__(self, definitions: list[FakeMCPDefinition], *, fail: bool = False) -> None:
        self.definitions = definitions
        self.fail = fail

    def assigned(self, _names: list[str]) -> list[FakeMCPDefinition]:
        return self.definitions

    async def connect_assigned(self, name: str) -> tuple[list[Any], list[str]]:
        if self.fail:
            raise ConnectionError("offline")
        return [SimpleNamespace(name=name)], [f"{name}__read"]


@pytest.mark.asyncio
async def test_mcp_assignment_degrades_only_optional_and_fails_required(tmp_path: Path) -> None:
    optional_runtime = FakeMCPRuntime([FakeMCPDefinition("optional-server", required=False)], fail=True)
    result = await MCPAssignmentResolver(optional_runtime).resolve_for_agent(definition(), context(tmp_path))
    assert result.degraded[0].required is False
    assert result.degraded[0].exception_type == "ConnectionError"

    required_runtime = FakeMCPRuntime([FakeMCPDefinition("required-server", required=True)], fail=True)
    with pytest.raises(MCPRequiredServerUnavailable, match="required-server"):
        await MCPAssignmentResolver(required_runtime).resolve_for_agent(
            definition(allowed_mcp=["required-server"]), context(tmp_path)
        )


@pytest.mark.asyncio
async def test_sdk_static_filter_never_contains_none_iterables() -> None:
    server = MCPFactory().create(
        MCPServerDefinition(
            name="filtered",
            transport="stdio",
            command="unused",
            allowed_tools=["read"],
        )
    )
    assert server.tool_filter == {"allowed_tool_names": ["read"]}
    raw = [SimpleNamespace(name="read"), SimpleNamespace(name="write")]
    filtered = await server._apply_tool_filter(raw, None, None)
    assert [item.name for item in filtered] == ["read"]

    unfiltered = MCPFactory().create(
        MCPServerDefinition(name="unfiltered", transport="stdio", command="unused")
    )
    assert unfiltered.tool_filter is None


def test_approval_checkpoint_and_argument_mutation_protection(tmp_path: Path) -> None:
    approvals = ApprovalStore(tmp_path / "approvals.sqlite")
    runtime_context = context(tmp_path)
    record = approvals.request(
        context=runtime_context,
        agent_id="test-agent",
        tool_name="write_text_file",
        tool_call_id="call-1",
        arguments={"path": "a.txt", "content": "one"},
        operation="replace",
        approving_user="operator",
        ttl_seconds=60,
        sdk_state_path="state.json",
    )
    checkpoints = RunCheckpointStore(tmp_path / "checkpoints")
    checkpoint = checkpoints.persist_waiting(
        run_id="run-1", approval_id=record.approval_id, state={"next": "call-1"}
    )
    assert checkpoint.status == "WAITING_FOR_APPROVAL"
    assert checkpoints.load_state("run-1") == {"next": "call-1"}

    approvals.approve(record.approval_id, approving_user="operator")
    with pytest.raises(PermissionError, match="arguments changed"):
        approvals.validate_resume(
            record.approval_id,
            context=runtime_context,
            tool_name="write_text_file",
            arguments={"path": "a.txt", "content": "two"},
            operation="replace",
        )
    assert approvals.inspect(record.approval_id).status == "rejected"


def test_evidence_recorder_owns_tool_and_file_facts(tmp_path: Path) -> None:
    recorder = RunEvidenceRecorder("run-1")
    result = execute_recorded(
        recorder,
        agent_id="test-agent",
        tool_name="write_text_file",
        arguments={"path": "a.txt", "content": "secret", "api_token": "hidden"},
        invoke=lambda: {
            "path": "a.txt",
            "sha256_before": None,
            "sha256_after": "a" * 64,
            "backup_path": None,
        },
    )
    assert result["path"] == "a.txt"
    evidence = recorder.evidence_for_run()
    assert len(evidence["agents"]["test-agent"]) == 1
    assert evidence["file_changes"][0]["action"] == "created"
    assert "hidden" not in str(evidence)


def test_nested_budget_scope_enforces_input_and_accounts_tools() -> None:
    ledger = BudgetLedger(soft_limit=100, hard_limit=120)
    ledger.register_scope(
        BudgetScope(
            scope_id="scope-1",
            agent_id="test-agent",
            input_limit=5,
            output_limit=10,
            total_limit=15,
        )
    )
    with pytest.raises(BudgetLimitExceeded, match="input budget"):
        ledger.enforce_input("test-agent", "this delegation is deliberately too long")
    ledger.record_tool(
        "read",
        0.25,
        failed=True,
        input_bytes=10,
        output_bytes=4,
        cost_units=0.5,
    )
    assert ledger.by_tool["read"].failures == 1
    assert ledger.by_tool["read"].input_bytes == 10


def test_runtime_events_are_redacted_hashed_and_inspectable(tmp_path: Path) -> None:
    log = EventLog(tmp_path)
    event = log.record_event(
        run_id="run-1",
        trace_id="trace-1",
        session_id="session-1",
        agent_ids=["test-agent"],
        skill_hashes={"test-skill": "a" * 64},
        event_type="approval_requested",
        severity="warning",
        details={"api_token": "never-store-me", "operation": "write"},
        evidence_references=["call-1"],
    )
    assert event.redacted_details["api_token"] == "[REDACTED]"
    assert "never-store-me" not in log.events_index.read_text(encoding="utf-8")
    assert log.inspect(event.event_id).details_digest == event.details_digest
    assert log.tail(1) == [event]
