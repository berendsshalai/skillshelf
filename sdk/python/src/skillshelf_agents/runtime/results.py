from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from ..contracts import Evidence, FileChange


class ArtifactReference(BaseModel):
    artifact_id: str = Field(min_length=1)
    path: str = Field(min_length=1)
    media_type: str = Field(min_length=1)
    sha256: str = Field(pattern=r"^[a-fA-F0-9]{64}$")
    size_bytes: int = Field(ge=0)


class TestExecution(BaseModel):
    command: list[str] = Field(min_length=1)
    exit_code: int
    duration_seconds: float = Field(ge=0)
    stdout_artifact_id: str | None = None
    stderr_artifact_id: str | None = None


class ToolExecutionEvidence(BaseModel):
    tool_call_id: str = Field(min_length=1)
    tool_name: str = Field(min_length=1)
    started_at: datetime
    completed_at: datetime
    status: Literal["completed", "failed", "denied", "timed_out"]
    input_digest: str = Field(pattern=r"^[a-fA-F0-9]{64}$")
    output_digest: str | None = Field(default=None, pattern=r"^[a-fA-F0-9]{64}$")
    error_code: str | None = None


class OperationalSpecialistResult(BaseModel):
    """Model interpretation plus fields that are overwritten by runtime evidence."""

    agent_id: str
    status: Literal["completed", "partially_completed", "blocked", "failed"]
    summary: str
    findings: list[str] = Field(default_factory=list)
    evidence: list[Evidence] = Field(default_factory=list)
    artifacts: list[ArtifactReference] = Field(default_factory=list)
    files_changed: list[FileChange] = Field(default_factory=list)
    tests_run: list[TestExecution] = Field(default_factory=list)
    tool_executions: list[ToolExecutionEvidence] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    next_action: str | None = None
    context_for_master: str = Field(max_length=6000)


class ExecutionEvidence(BaseModel):
    artifacts: list[ArtifactReference] = Field(default_factory=list)
    files_changed: list[FileChange] = Field(default_factory=list)
    tests_run: list[TestExecution] = Field(default_factory=list)
    tool_executions: list[ToolExecutionEvidence] = Field(default_factory=list)


def merge_mechanical_evidence(
    model_result: OperationalSpecialistResult,
    mechanical: ExecutionEvidence,
) -> OperationalSpecialistResult:
    """Discard model-authored execution claims and attach recorded facts."""
    return model_result.model_copy(
        update={
            "artifacts": list(mechanical.artifacts),
            "files_changed": list(mechanical.files_changed),
            "tests_run": list(mechanical.tests_run),
            "tool_executions": list(mechanical.tool_executions),
        }
    )
