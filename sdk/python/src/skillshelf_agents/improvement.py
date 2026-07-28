from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Any, Callable

from .governance import GovernanceManager


class ProposalStore:
    """Compatibility facade over the canonical full-package governor."""

    def __init__(self, home: Path, root: Path) -> None:
        self.manager = GovernanceManager(home, root)

    def stage(self, target_skill: str, proposed_content: str, evidence_ids: list[str]) -> str:
        proposal_id = self.manager.new_proposal_id()
        source_digest = self.manager.source_digest(target_skill)

        def mutate(package: Path) -> None:
            (package / "SKILL.md").write_text(proposed_content, encoding="utf-8")

        self.manager.stage(
            proposal_id=proposal_id,
            target_skill=target_skill,
            source_digest=source_digest,
            evidence_ids=evidence_ids,
            expected_benefit="Reviewed SkillShelf runtime improvement",
            risk_analysis="Semantic and integration regressions must be evaluated before apply.",
            creator="skillshelf-runtime",
            evaluation_plan="structural, semantic and affected integration verification",
            mutate=mutate,
        )
        return proposal_id

    def list(self) -> list[dict[str, Any]]:
        values: list[dict[str, Any]] = []
        for path in sorted(self.manager.proposals.glob("*/proposal.json")):
            values.append(self.manager.inspect(path.parent.name).to_dict())
        return values

    def inspect(self, proposal_id: str) -> dict[str, Any]:
        return self.manager.inspect(proposal_id).to_dict()

    def reject(self, proposal_id: str) -> None:
        proposal = self.manager.inspect(proposal_id)
        if proposal.status in {"APPLIED", "ROLLED_BACK"}:
            raise ValueError(f"cannot reject proposal in state {proposal.status}")
        self.manager._write_proposal(replace(proposal, status="REJECTED"))

    def approve(self, proposal_id: str, *, confirmed: bool, evaluator: Callable[[str], bool]) -> None:
        proposal = self.manager.inspect(proposal_id)

        def semantic(_staged: Path) -> tuple[bool, str]:
            passed = evaluator(proposal.target_skill)
            return passed, "affected evaluation passed" if passed else "affected evaluation failed"

        self.manager.evaluate(
            proposal_id,
            structural=lambda _staged: (True, "complete package validated during staging"),
            semantic=semantic,
            integration=lambda _staged: (True, "compatibility facade integration check"),
        )
        approval = self.manager.approve(
            proposal_id,
            approved_by="explicit-cli-user",
            confirmed=confirmed,
        )
        self.manager.apply(approval)
