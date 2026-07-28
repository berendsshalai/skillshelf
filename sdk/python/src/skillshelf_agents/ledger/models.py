from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class RunStatus(StrEnum):
    CREATED = "CREATED"
    ROUTED = "ROUTED"
    RUNNING = "RUNNING"
    WAITING_FOR_APPROVAL = "WAITING_FOR_APPROVAL"
    RETRYING = "RETRYING"
    COMPLETED = "COMPLETED"
    PARTIALLY_COMPLETED = "PARTIALLY_COMPLETED"
    FAILED = "FAILED"
    TIMED_OUT = "TIMED_OUT"
    CANCELLED = "CANCELLED"


TERMINAL_RUN_STATUSES = {
    RunStatus.COMPLETED,
    RunStatus.PARTIALLY_COMPLETED,
    RunStatus.FAILED,
    RunStatus.TIMED_OUT,
    RunStatus.CANCELLED,
}


class ToolCallStatus(StrEnum):
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    DENIED = "denied"
    TIMED_OUT = "timed_out"


class ToolCallRecord(BaseModel):
    tool_call_id: str
    agent_id: str
    tool_name: str
    status: ToolCallStatus
    arguments_digest: str
    output_digest: str | None = None
    started_at: datetime
    completed_at: datetime | None = None
    error_code: str | None = None


class UsageRecord(BaseModel):
    request_id: str
    agent_id: str
    input_tokens: int
    cached_tokens: int
    reasoning_tokens: int
    output_tokens: int
    total_tokens: int


class ErrorRecord(BaseModel):
    code: str
    message: str
    created_at: datetime


class RunRecord(BaseModel):
    run_id: str
    trace_id: str
    session_id: str
    status: RunStatus
    canonical_input: dict[str, Any]
    configuration_version: str
    created_at: datetime
    updated_at: datetime
    tool_calls: list[ToolCallRecord] = Field(default_factory=list)
    usage: list[UsageRecord] = Field(default_factory=list)
    errors: list[ErrorRecord] = Field(default_factory=list)
