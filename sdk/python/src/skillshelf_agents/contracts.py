from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


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
    status: str
    summary: str
    findings: list[str] = Field(default_factory=list)
    evidence: list[Evidence] = Field(default_factory=list)
    files_changed: list[FileChange] = Field(default_factory=list)
    tests_run: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    next_action: str | None = None
    context_for_master: str = Field(description="Compact context for the master; large artifacts use paths.")


class GovernanceProposal(BaseModel):
    proposal_id: str
    target_skill: str
    evidence_ids: list[str]
    problem: str
    proposed_change: str
    expected_benefit: str
    regression_risks: list[str] = Field(default_factory=list)
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
    tests_run: list[str] = Field(default_factory=list)
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
