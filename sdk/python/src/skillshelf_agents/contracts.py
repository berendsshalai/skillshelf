from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


class Severity(StrEnum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class Evidence(BaseModel):
    source: str
    summary: str
    location: str | None = None
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)


class FileChange(BaseModel):
    path: str
    action: str
    summary: str


class TestExecution(BaseModel):
    command: str
    status: Literal["passed", "failed", "skipped"]
    exit_code: int | None = None
    artifact_id: str | None = None


class ArtifactReference(BaseModel):
    artifact_id: str
    path: str
    media_type: str
    sha256: str
    size_bytes: int = Field(ge=0)


class ToolExecutionEvidence(BaseModel):
    tool_call_id: str
    tool_name: str
    started_at: datetime
    completed_at: datetime
    status: Literal["completed", "failed", "denied", "timed_out"]
    input_digest: str
    output_digest: str | None = None
    error_code: str | None = None


class UsageSummary(BaseModel):
    requests: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    cached_tokens: int = 0
    reasoning_tokens: int = 0
    total_tokens: int = 0
    budget_exceeded: bool = False


class SpecialistResult(BaseModel):
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
    context_for_master: str = Field(
        default="",
        max_length=6000,
        description="Compact context for the master; large artifacts use paths.",
    )

    @field_validator("status", mode="before")
    @classmethod
    def normalise_legacy_status(cls, value: object) -> object:
        return "completed" if value == "complete" else value

    @field_validator("tests_run", mode="before")
    @classmethod
    def normalise_legacy_tests(cls, value: object) -> object:
        if isinstance(value, list):
            return [
                {"command": item, "status": "passed"} if isinstance(item, str) else item for item in value
            ]
        return value


class GovernanceProposal(BaseModel):
    proposal_id: str
    target_skill: str
    evidence_ids: list[str]
    source_digest: str = ""
    staged_digest: str = ""
    problem: str
    proposed_change: str
    expected_benefit: str
    regression_risks: list[str] = Field(default_factory=list)
    risk_analysis: list[str] = Field(default_factory=list)
    creator: str = "unknown"
    evaluation_plan: list[str] = Field(default_factory=list)
    created_at: datetime | None = None
    status: str = "staged"
    staged_path: str | None = None
    approval_required: bool = True


class GovernanceResult(SpecialistResult):
    observations_recorded: list[str] = Field(default_factory=list)
    proposals: list[GovernanceProposal] = Field(default_factory=list)


class OrchestratorResult(BaseModel):
    status: str
    answer: str
    specialists_used: list[str] = Field(default_factory=list)
    evidence: list[Evidence] = Field(default_factory=list)
    files_changed: list[FileChange] = Field(default_factory=list)
    tests_run: list[TestExecution] = Field(default_factory=list)
    unresolved_risks: list[str] = Field(default_factory=list)
    usage: UsageSummary = Field(default_factory=UsageSummary)


class RouteDecision(BaseModel):
    direct_agent: str | None = None
    candidate_agents: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)
    reasons: list[str] = Field(default_factory=list)
    requires_master: bool = True


class Observation(BaseModel):
    run_id: str
    timestamp: str
    agents_used: list[str]
    skills_used: list[str]
    routing_decision: dict[str, Any]
    usage: dict[str, Any]
    tool_failures: list[str]
    guardrail_events: list[str]
    user_corrections: list[str]
    evaluation_failures: list[str]
    possible_improvement: bool = False
