from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class EvaluationRecord:
    name: str
    passed: bool
    detail: str
    completed_at: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "EvaluationRecord":
        return cls(
            name=str(value["name"]),
            passed=bool(value["passed"]),
            detail=str(value["detail"]),
            completed_at=str(value["completed_at"]),
        )


@dataclass(frozen=True)
class Proposal:
    proposal_id: str
    target_skill: str
    source_digest: str
    staged_digest: str
    evidence_ids: tuple[str, ...]
    expected_benefit: str
    risk_analysis: str
    created_at: str
    creator: str
    evaluation_plan: str
    status: str
    live_path: str
    staged_path: str
    evaluations: tuple[EvaluationRecord, ...] = ()
    final_digest: str | None = None

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["evidence_ids"] = list(self.evidence_ids)
        value["evaluations"] = [item.to_dict() for item in self.evaluations]
        return value

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "Proposal":
        return cls(
            proposal_id=str(value["proposal_id"]),
            target_skill=str(value["target_skill"]),
            source_digest=str(value["source_digest"]),
            staged_digest=str(value["staged_digest"]),
            evidence_ids=tuple(str(item) for item in value["evidence_ids"]),
            expected_benefit=str(value["expected_benefit"]),
            risk_analysis=str(value["risk_analysis"]),
            created_at=str(value["created_at"]),
            creator=str(value["creator"]),
            evaluation_plan=str(value["evaluation_plan"]),
            status=str(value["status"]),
            live_path=str(value["live_path"]),
            staged_path=str(value["staged_path"]),
            evaluations=tuple(EvaluationRecord.from_dict(item) for item in value.get("evaluations", [])),
            final_digest=(str(value["final_digest"]) if value.get("final_digest") is not None else None),
        )


@dataclass(frozen=True)
class Approval:
    approval_id: str
    proposal_id: str
    target_skill: str
    source_digest: str
    staged_digest: str
    approved_by: str
    approved_at: str
    binding_digest: str

    def to_dict(self) -> dict[str, str]:
        return asdict(self)

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "Approval":
        return cls(
            approval_id=str(value["approval_id"]),
            proposal_id=str(value["proposal_id"]),
            target_skill=str(value["target_skill"]),
            source_digest=str(value["source_digest"]),
            staged_digest=str(value["staged_digest"]),
            approved_by=str(value["approved_by"]),
            approved_at=str(value["approved_at"]),
            binding_digest=str(value["binding_digest"]),
        )
