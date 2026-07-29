from __future__ import annotations

import hashlib
import json
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from filelock import FileLock
from pydantic import BaseModel, Field

from .contracts import Observation
from .tracing import sanitise_event


class RuntimeEvent(BaseModel):
    event_id: str
    run_id: str
    trace_id: str
    session_id: str
    agent_ids: list[str] = Field(default_factory=list)
    skill_hashes: dict[str, str] = Field(default_factory=dict)
    timestamp: datetime
    event_type: str
    severity: Literal["info", "warning", "error", "critical"]
    redacted_details: dict[str, Any] = Field(default_factory=dict)
    details_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    evidence_references: list[str] = Field(default_factory=list)


class EventLog:
    def __init__(self, directory: Path) -> None:
        self.directory = directory
        self.directory.mkdir(parents=True, exist_ok=True)
        self.index = self.directory / "observations.jsonl"
        self.events_index = self.directory / "events.jsonl"

    def append(self, observation: Observation) -> None:
        line = observation.model_dump_json() + "\n"
        with FileLock(str(self.index) + ".lock"):
            with self.index.open("a", encoding="utf-8") as stream:
                stream.write(line)

    def read(self) -> list[Observation]:
        if not self.index.exists():
            return []
        return [
            Observation.model_validate_json(line)
            for line in self.index.read_text(encoding="utf-8").splitlines()
        ]

    def record_event(
        self,
        *,
        run_id: str,
        trace_id: str,
        session_id: str,
        event_type: str,
        severity: Literal["info", "warning", "error", "critical"],
        agent_ids: list[str] | None = None,
        skill_hashes: dict[str, str] | None = None,
        details: dict[str, Any] | None = None,
        evidence_references: list[str] | None = None,
    ) -> RuntimeEvent:
        safe = sanitise_event(details or {})
        canonical = json.dumps(safe, sort_keys=True, separators=(",", ":"), default=str)
        item = RuntimeEvent(
            event_id=f"event-{uuid.uuid4().hex}",
            run_id=run_id,
            trace_id=trace_id,
            session_id=session_id,
            agent_ids=agent_ids or [],
            skill_hashes=skill_hashes or {},
            timestamp=datetime.now(UTC),
            event_type=event_type,
            severity=severity,
            redacted_details=safe,
            details_digest=hashlib.sha256(canonical.encode()).hexdigest(),
            evidence_references=evidence_references or [],
        )
        with FileLock(str(self.events_index) + ".lock"):
            with self.events_index.open("a", encoding="utf-8") as stream:
                stream.write(item.model_dump_json() + "\n")
        return item

    def events(self) -> list[RuntimeEvent]:
        if not self.events_index.is_file():
            return []
        return [
            RuntimeEvent.model_validate_json(line)
            for line in self.events_index.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]

    def tail(self, limit: int = 50) -> list[RuntimeEvent]:
        if limit < 1 or limit > 1000:
            raise ValueError("limit must be between 1 and 1000")
        return self.events()[-limit:]

    def inspect(self, event_id: str) -> RuntimeEvent:
        for item in self.events():
            if item.event_id == event_id:
                return item
        raise KeyError(event_id)

    def export(self, destination: Path) -> Path:
        resolved = destination.resolve()
        resolved.parent.mkdir(parents=True, exist_ok=True)
        payload = [item.model_dump(mode="json") for item in self.events()]
        resolved.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        return resolved
