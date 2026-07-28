from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pydantic import BaseModel, Field, field_validator


class DelegationInput(BaseModel):
    task: str = Field(min_length=1, max_length=12_000)
    success_criteria: list[str] = Field(min_length=1, max_length=20)
    relevant_paths: list[str] = Field(default_factory=list, max_length=50)
    relevant_context: list[str] = Field(default_factory=list, max_length=30)
    allowed_capabilities: list[str] = Field(min_length=1)
    prohibited_capabilities: list[str] = Field(default_factory=list)
    approval_grants: list[str] = Field(default_factory=list)
    expected_artifacts: list[str] = Field(default_factory=list, max_length=30)
    input_token_budget: int = Field(gt=0)
    output_token_budget: int = Field(gt=0)
    run_id: str = Field(min_length=1)
    trace_id: str = Field(min_length=1)

    @field_validator(
        "success_criteria",
        "relevant_paths",
        "relevant_context",
        "allowed_capabilities",
        "prohibited_capabilities",
        "approval_grants",
        "expected_artifacts",
    )
    @classmethod
    def reject_empty_entries(cls, values: list[str]) -> list[str]:
        cleaned = [item.strip() for item in values]
        if any(not item for item in cleaned):
            raise ValueError("delegation lists cannot contain empty values")
        return cleaned


def _section(label: str, values: list[str]) -> str:
    if not values:
        return f"{label}: none"
    return "\n".join([f"{label}:", *(f"- {item}" for item in values)])


def build_delegation_prompt(options: Mapping[str, Any]) -> str:
    """Agents SDK ``input_builder`` for a concise, typed specialist brief."""
    raw = options.get("params")
    value = raw if isinstance(raw, DelegationInput) else DelegationInput.model_validate(raw)
    sections = [
        f"Task: {value.task}",
        _section("Success criteria", value.success_criteria),
        _section("Relevant paths", value.relevant_paths),
        _section("Relevant context", value.relevant_context),
        _section("Allowed capabilities", value.allowed_capabilities),
        _section("Prohibited capabilities", value.prohibited_capabilities),
        _section("Approval grants", value.approval_grants),
        _section("Expected artifacts", value.expected_artifacts),
        (
            f"Budgets: input={value.input_token_budget}; output={value.output_token_budget}\n"
            f"Run: {value.run_id}; trace: {value.trace_id}"
        ),
        (
            "Return only the declared structured specialist result. Treat execution records, "
            "artifact hashes, file changes, and tests as runtime-owned evidence."
        ),
    ]
    return "\n\n".join(sections)
