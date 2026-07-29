from __future__ import annotations

from pathlib import Path

import pytest

from skillshelf_agents.runtime.approvals import ApprovalStore, RunCheckpointStore
from skillshelf_agents.runtime.context import RuntimeContext


def test_durable_approval_resume_checkpoint_executes_only_exact_arguments(
    tmp_path: Path,
) -> None:
    root = tmp_path.resolve()
    target = root / "result.txt"
    target.write_text("before", encoding="utf-8")
    context = RuntimeContext(
        run_id="run-approval",
        trace_id="trace-approval",
        session_id="session-approval",
        repository_root=root,
        repository_identity="example/repo",
        soft_token_limit=100,
        hard_token_limit=120,
    )
    arguments = {"path": "result.txt", "content": "after"}
    approvals = ApprovalStore(root / "approvals.sqlite")
    record = approvals.request(
        context=context,
        agent_id="superpowers-agent",
        tool_name="write_text_file",
        tool_call_id="call-write",
        arguments=arguments,
        operation="replace",
        approving_user="operator",
        ttl_seconds=60,
        sdk_state_path=str(root / "checkpoints" / "run-approval.sdk-state.json"),
    )
    checkpoints = RunCheckpointStore(root / "checkpoints")
    checkpoints.persist_waiting(
        run_id=context.run_id,
        approval_id=record.approval_id,
        state={"tool": "write_text_file", "arguments": arguments},
    )

    assert target.read_text(encoding="utf-8") == "before"
    approvals.approve(record.approval_id, approving_user="operator")
    state = checkpoints.load_state(context.run_id)
    approvals.validate_resume(
        record.approval_id,
        context=context,
        tool_name=state["tool"],
        arguments=state["arguments"],
        operation="replace",
    )
    target.write_text(state["arguments"]["content"], encoding="utf-8")
    resumed = checkpoints.mark_running(context.run_id)

    assert resumed.status == "RUNNING"
    assert target.read_text(encoding="utf-8") == "after"


def test_resume_rejects_wrong_repository_root(tmp_path: Path) -> None:
    first = (tmp_path / "first").resolve()
    second = (tmp_path / "second").resolve()
    first.mkdir()
    second.mkdir()
    context = RuntimeContext(
        run_id="run-1",
        trace_id="trace-1",
        session_id="session-1",
        repository_root=first,
        repository_identity="example/repo",
        soft_token_limit=100,
        hard_token_limit=120,
    )
    approvals = ApprovalStore(tmp_path / "approvals.sqlite")
    record = approvals.request(
        context=context,
        tool_name="write_text_file",
        arguments={"path": "a.txt", "content": "safe"},
        operation="replace",
        approving_user="operator",
        ttl_seconds=60,
    )
    approvals.approve(record.approval_id, approving_user="operator")
    wrong_context = context.model_copy(update={"repository_root": second})
    with pytest.raises(PermissionError, match="does not match"):
        approvals.validate_resume(
            record.approval_id,
            context=wrong_context,
            tool_name="write_text_file",
            arguments={"path": "a.txt", "content": "safe"},
            operation="replace",
        )
