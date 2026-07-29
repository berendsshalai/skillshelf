from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field, model_validator


class WorkflowState(StrEnum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    WAITING_FOR_APPROVAL = "WAITING_FOR_APPROVAL"
    WAITING_FOR_EXTERNAL_EVENT = "WAITING_FOR_EXTERNAL_EVENT"
    RETRYING = "RETRYING"
    COMPLETED = "COMPLETED"
    PARTIALLY_COMPLETED = "PARTIALLY_COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    DEAD_LETTERED = "DEAD_LETTERED"


class RetryPolicy(BaseModel):
    maximum_attempts: int = Field(default=3, ge=1, le=100)
    base_delay_seconds: float = Field(default=1.0, ge=0, le=86_400)
    maximum_delay_seconds: float = Field(default=300.0, ge=0, le=604_800)
    retryable_errors: tuple[str, ...] = ("TimeoutError", "ConnectionError")

    def delay(self, attempt: int) -> float:
        return float(min(self.base_delay_seconds * (2 ** max(0, attempt - 1)), self.maximum_delay_seconds))


class WorkflowStepDefinition(BaseModel):
    id: str = Field(pattern=r"^[a-z][a-z0-9-]{1,63}$")
    handler: str
    retry_policy: RetryPolicy = Field(default_factory=RetryPolicy)
    approval_policy: str | None = None
    compensation_handler: str | None = None


class WorkflowDefinition(BaseModel):
    id: str = Field(pattern=r"^[a-z][a-z0-9-]{1,63}$")
    version: int = Field(ge=1)
    input_schema: str
    steps: list[WorkflowStepDefinition]

    @model_validator(mode="after")
    def distinct_steps(self) -> "WorkflowDefinition":
        identifiers = [step.id for step in self.steps]
        if not identifiers or len(identifiers) != len(set(identifiers)):
            raise ValueError("workflow steps must be non-empty and distinct")
        return self
