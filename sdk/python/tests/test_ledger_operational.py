from __future__ import annotations

from pathlib import Path

from skillshelf_agents.ledger.models import RunStatus, ToolCallStatus
from skillshelf_agents.ledger.repository import RunLedger


def test_run_ledger_records_lifecycle_tools_usage_and_terminal_error(tmp_path: Path) -> None:
    ledger = RunLedger(tmp_path / "runtime.sqlite")
    ledger.create_run(
        run_id="run-1",
        trace_id="trace-1",
        session_id="session-1",
        canonical_input={"task": "inspect"},
        configuration_version="0.4.0",
    )
    ledger.transition("run-1", RunStatus.ROUTED)
    ledger.transition("run-1", RunStatus.RUNNING)
    ledger.start_tool_call(
        run_id="run-1",
        tool_call_id="call-1",
        agent_id="memory-agent",
        tool_name="read_text_file",
        arguments_digest="a" * 64,
    )
    ledger.finish_tool_call(
        "call-1",
        status=ToolCallStatus.COMPLETED,
        output_digest="b" * 64,
    )
    ledger.record_usage(
        run_id="run-1",
        agent_id="memory-agent",
        request_id="request-1",
        input_tokens=10,
        cached_tokens=2,
        reasoning_tokens=3,
        output_tokens=5,
    )
    ledger.record_error("run-1", code="MODEL_FAILED", message="provider unavailable")
    ledger.transition("run-1", RunStatus.FAILED)

    record = ledger.inspect_run("run-1")

    assert record.status == RunStatus.FAILED
    assert record.tool_calls[0].status == ToolCallStatus.COMPLETED
    assert record.usage[0].total_tokens == 15
    assert record.errors[0].code == "MODEL_FAILED"


def test_run_ledger_rejects_invalid_terminal_transition(tmp_path: Path) -> None:
    ledger = RunLedger(tmp_path / "runtime.sqlite")
    ledger.create_run(
        run_id="run-1",
        trace_id="trace-1",
        session_id="session-1",
        canonical_input={"task": "inspect"},
        configuration_version="0.4.0",
    )
    ledger.transition("run-1", RunStatus.COMPLETED)

    try:
        ledger.transition("run-1", RunStatus.RUNNING)
    except ValueError as error:
        assert "terminal" in str(error)
    else:
        raise AssertionError("terminal run was incorrectly reopened")
