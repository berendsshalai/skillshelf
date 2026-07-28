from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, Field, field_validator, model_validator


class RuntimeContext(BaseModel):
    """Per-run state passed through the Agents SDK context wrapper."""

    run_id: str = Field(min_length=1)
    trace_id: str = Field(min_length=1)
    session_id: str = Field(min_length=1)
    repository_root: Path
    repository_identity: str = Field(min_length=1)
    approval_grants: set[str] = Field(default_factory=set)
    soft_token_limit: int = Field(gt=0)
    hard_token_limit: int = Field(gt=0)
    delegation_depth: int = Field(default=0, ge=0)
    max_delegation_depth: int = Field(default=2, ge=0)

    @field_validator("repository_root")
    @classmethod
    def normalize_root(cls, value: Path) -> Path:
        return value.expanduser().resolve()

    @model_validator(mode="after")
    def validate_limits(self) -> "RuntimeContext":
        if self.hard_token_limit < self.soft_token_limit:
            raise ValueError("hard_token_limit must be at least soft_token_limit")
        if self.delegation_depth > self.max_delegation_depth:
            raise ValueError("delegation depth exceeds its configured maximum")
        return self

    def child(self) -> "RuntimeContext":
        """Return a copied context for one bounded nested delegation."""
        return self.model_copy(update={"delegation_depth": self.delegation_depth + 1})
