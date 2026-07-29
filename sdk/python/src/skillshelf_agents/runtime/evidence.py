from __future__ import annotations

import hashlib
import json
import time
import uuid
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable, Literal, TypeVar

from pydantic import BaseModel, Field

from ..contracts import Evidence, FileChange
from ..ledger.models import ToolCallStatus
from .results import (
    ArtifactReference,
    ExecutionEvidence,
    TestExecution,
    ToolExecutionEvidence,
)

T = TypeVar("T")


def canonical_digest(value: Any) -> str:
    safe = _redact(value)
    payload = json.dumps(safe, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class MechanicalFileChange(BaseModel):
    path: str
    action: Literal["created", "modified", "deleted"]
    before_sha256: str | None
    after_sha256: str | None
    backup_path: str | None
    tool_call_id: str


class RecordedTestExecution(BaseModel):
    command: list[str] = Field(min_length=1)
    working_directory: str
    exit_code: int
    duration_seconds: float
    stdout_artifact_id: str
    stderr_artifact_id: str
    tool_call_id: str


class RunEvidenceRecorder:
    """Run-owned evidence. Model output is never an authority for these records."""

    def __init__(self, run_id: str, *, ledger: Any | None = None) -> None:
        self.run_id = run_id
        self.ledger = ledger
        self._started: dict[str, tuple[str, str, float, str]] = {}
        self._agent_tools: dict[str, list[ToolExecutionEvidence]] = defaultdict(list)
        self._file_changes: list[MechanicalFileChange] = []
        self._artifacts: list[ArtifactReference] = []
        self._tests: list[RecordedTestExecution] = []
        self._mcp_connections: list[dict[str, Any]] = []
        self._guardrails: list[dict[str, Any]] = []

    def start_tool_call(
        self,
        *,
        agent_id: str,
        tool_name: str,
        arguments: dict[str, Any],
        tool_call_id: str | None = None,
    ) -> str:
        identifier = tool_call_id or f"call-{uuid.uuid4().hex}"
        digest = canonical_digest(arguments)
        self._started[identifier] = (agent_id, tool_name, time.monotonic(), digest)
        if self.ledger is not None:
            self.ledger.start_tool_call(
                run_id=self.run_id,
                tool_call_id=identifier,
                agent_id=agent_id,
                tool_name=tool_name,
                arguments_digest=digest,
            )
        return identifier

    def complete_tool_call(self, tool_call_id: str, output: Any) -> None:
        self._finish(tool_call_id, status="completed", output_digest=canonical_digest(output))

    def fail_tool_call(
        self,
        tool_call_id: str,
        exception: BaseException,
        *,
        error_code: str | None = None,
    ) -> None:
        self._finish(
            tool_call_id,
            status="failed",
            error_code=error_code or type(exception).__name__,
        )

    def _finish(
        self,
        tool_call_id: str,
        *,
        status: Literal["completed", "failed", "denied", "timed_out"],
        output_digest: str | None = None,
        error_code: str | None = None,
    ) -> None:
        agent_id, tool_name, started, input_digest = self._started.pop(tool_call_id)
        now = datetime.now(UTC)
        started_wall = datetime.fromtimestamp(now.timestamp() - (time.monotonic() - started), tz=UTC)
        item = ToolExecutionEvidence(
            tool_call_id=tool_call_id,
            tool_name=tool_name,
            started_at=started_wall,
            completed_at=now,
            status=status,
            input_digest=input_digest,
            output_digest=output_digest,
            error_code=error_code,
        )
        self._agent_tools[agent_id].append(item)
        if self.ledger is not None:
            self.ledger.finish_tool_call(
                tool_call_id,
                status=ToolCallStatus(status),
                output_digest=output_digest,
                error_code=error_code,
            )

    def record_file_change(
        self,
        *,
        path: str,
        action: Literal["created", "modified", "deleted"],
        before_sha256: str | None,
        after_sha256: str | None,
        backup_path: str | None,
        tool_call_id: str,
    ) -> MechanicalFileChange:
        item = MechanicalFileChange(
            path=path,
            action=action,
            before_sha256=before_sha256,
            after_sha256=after_sha256,
            backup_path=backup_path,
            tool_call_id=tool_call_id,
        )
        self._file_changes.append(item)
        return item

    def record_artifact(self, artifact: Any) -> ArtifactReference:
        item = ArtifactReference.model_validate(artifact)
        self._artifacts.append(item)
        return item

    def record_test_execution(self, execution: Any) -> RecordedTestExecution:
        item = RecordedTestExecution.model_validate(execution)
        self._tests.append(item)
        return item

    def record_mcp_connection(self, **event: Any) -> None:
        self._mcp_connections.append(_redact(event))

    def record_guardrail_event(self, **event: Any) -> None:
        self._guardrails.append(_redact(event))

    def evidence_for_agent_invocation(self, agent_id: str) -> ExecutionEvidence:
        return ExecutionEvidence(
            artifacts=list(self._artifacts),
            files_changed=[
                FileChange(
                    path=item.path,
                    action=item.action,
                    summary=(
                        f"{item.before_sha256 or 'absent'} -> {item.after_sha256 or 'absent'} "
                        f"(tool {item.tool_call_id})"
                    ),
                )
                for item in self._file_changes
            ],
            tests_run=[
                TestExecution(
                    command=item.command,
                    exit_code=item.exit_code,
                    duration_seconds=item.duration_seconds,
                    stdout_artifact_id=item.stdout_artifact_id,
                    stderr_artifact_id=item.stderr_artifact_id,
                )
                for item in self._tests
            ],
            tool_executions=list(self._agent_tools.get(agent_id, [])),
        )

    def evidence_for_run(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "agents": {
                agent: [item.model_dump(mode="json") for item in items]
                for agent, items in self._agent_tools.items()
            },
            "file_changes": [item.model_dump(mode="json") for item in self._file_changes],
            "artifacts": [item.model_dump(mode="json") for item in self._artifacts],
            "tests": [item.model_dump(mode="json") for item in self._tests],
            "mcp_connections": list(self._mcp_connections),
            "guardrail_events": list(self._guardrails),
        }


def execute_recorded(
    recorder: RunEvidenceRecorder | None,
    *,
    agent_id: str,
    tool_name: str,
    arguments: dict[str, Any],
    invoke: Callable[[], T],
) -> T:
    if recorder is None:
        return invoke()
    call_id = recorder.start_tool_call(agent_id=agent_id, tool_name=tool_name, arguments=arguments)
    try:
        output = invoke()
    except BaseException as exc:
        recorder.fail_tool_call(call_id, exc)
        raise
    recorder.complete_tool_call(call_id, output)
    _collect_output_evidence(recorder, call_id, tool_name, arguments, output)
    return output


def validate_evidence_references(entries: list[Evidence], recorded: dict[str, Any]) -> list[Evidence]:
    payload = json.dumps(recorded, sort_keys=True, default=str)
    validated: list[Evidence] = []
    for entry in entries:
        grounded = bool(entry.location and entry.location in payload)
        if grounded:
            validated.append(entry)
        else:
            validated.append(
                entry.model_copy(
                    update={
                        "source": "model_interpretation",
                        "confidence": min(entry.confidence, 0.5),
                    }
                )
            )
    return validated


def _collect_output_evidence(
    recorder: RunEvidenceRecorder,
    call_id: str,
    tool_name: str,
    arguments: dict[str, Any],
    output: Any,
) -> None:
    values = output if isinstance(output, list) else [output]
    for value in values:
        if not isinstance(value, dict):
            continue
        if {"path", "sha256_after"}.issubset(value):
            recorder.record_file_change(
                path=str(value["path"]),
                action="modified" if value.get("sha256_before") else "created",
                before_sha256=value.get("sha256_before"),
                after_sha256=value.get("sha256_after"),
                backup_path=value.get("backup_path"),
                tool_call_id=call_id,
            )
        if tool_name == "run_safe_command" and _is_test_command(arguments):
            request = arguments.get("request", arguments)
            recorder.record_test_execution(
                {
                    "command": [request.get("executable", ""), *request.get("arguments", [])],
                    "working_directory": value["working_directory"],
                    "exit_code": value["exit_code"],
                    "duration_seconds": value["duration_seconds"],
                    "stdout_artifact_id": value["stdout_artifact_id"],
                    "stderr_artifact_id": value["stderr_artifact_id"],
                    "tool_call_id": call_id,
                }
            )


def _is_test_command(arguments: dict[str, Any]) -> bool:
    request = arguments.get("request", arguments)
    executable = str(request.get("executable", "")).casefold()
    values = " ".join(str(item) for item in request.get("arguments", [])).casefold()
    return executable == "pytest" or "pytest" in values or " test" in f" {values}"


def _redact(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: (
                "[REDACTED]"
                if any(token in key.casefold() for token in ("token", "password", "secret", "key"))
                else _redact(item)
            )
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_redact(item) for item in value]
    if isinstance(value, Path):
        return str(value)
    return value
