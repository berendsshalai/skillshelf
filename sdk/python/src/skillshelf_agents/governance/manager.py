from __future__ import annotations

import uuid
from dataclasses import replace
from pathlib import Path
from typing import Callable

from .models import Approval, EvaluationRecord, Proposal
from .safety import (
    SAFE_IDENTIFIER,
    SAFE_PROPOSAL_ID,
    SHA256,
    SafetyError,
    OwnedFileLock,
    atomic_replace,
    atomic_write_json,
    binding_digest,
    copy_package,
    ensure_relative_to,
    package_digest,
    read_json,
    remove_tree,
    utc_now,
    validate_package,
)

Evaluator = Callable[[Path], bool | tuple[bool, str]]
Mutator = Callable[[Path], None]
FaultInjector = Callable[[str], None]


class GovernanceError(SafetyError):
    pass


class GovernanceManager:
    """Stage, evaluate and atomically apply complete skill packages."""

    def __init__(self, home: Path, repository_root: Path) -> None:
        self.home = home.resolve(strict=False)
        self.repository_root = repository_root.resolve(strict=True)
        self.root = self.home / "governance"
        self.proposals = self.root / "proposals"
        self.backups = self.root / "backups"
        self.journals = self.root / "journals"
        self.locks = self.root / "locks"
        for path in (self.proposals, self.backups, self.journals, self.locks):
            path.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def new_proposal_id() -> str:
        return f"proposal-{uuid.uuid4().hex[:16]}"

    def source_digest(self, target_skill: str) -> str:
        return package_digest(self._live_skill(target_skill))

    def stage(
        self,
        *,
        proposal_id: str,
        target_skill: str,
        source_digest: str,
        evidence_ids: list[str],
        expected_benefit: str,
        risk_analysis: str,
        creator: str,
        evaluation_plan: str,
        mutate: Mutator,
    ) -> Proposal:
        self._validate_proposal_inputs(
            proposal_id=proposal_id,
            target_skill=target_skill,
            source_digest=source_digest,
            evidence_ids=evidence_ids,
            expected_benefit=expected_benefit,
            risk_analysis=risk_analysis,
            creator=creator,
            evaluation_plan=evaluation_plan,
        )
        live = self._live_skill(target_skill)
        fresh_digest = package_digest(live)
        if fresh_digest != source_digest:
            raise GovernanceError("expected source digest does not match the live package")

        proposal_directory = self._proposal_directory(proposal_id)
        if proposal_directory.exists():
            raise GovernanceError(f"proposal already exists: {proposal_id}")
        proposal_directory.mkdir()
        staged = proposal_directory / "package"
        try:
            copy_package(live, staged)
            validate_package(staged, create_missing_directories=True)
            mutate(staged)
            staged_digest = package_digest(staged)
            if package_digest(live) != source_digest:
                raise GovernanceError("live package changed while the proposal was staged")
            proposal = Proposal(
                proposal_id=proposal_id,
                target_skill=target_skill,
                source_digest=source_digest,
                staged_digest=staged_digest,
                evidence_ids=tuple(evidence_ids),
                expected_benefit=expected_benefit.strip(),
                risk_analysis=risk_analysis.strip(),
                created_at=utc_now(),
                creator=creator.strip(),
                evaluation_plan=evaluation_plan.strip(),
                status="STAGED",
                live_path=str(live),
                staged_path=str(staged),
            )
            self._write_proposal(proposal)
            return proposal
        except Exception:
            remove_tree(proposal_directory)
            raise

    def evaluate(
        self,
        proposal_id: str,
        *,
        structural: Evaluator,
        semantic: Evaluator,
        integration: Evaluator,
    ) -> Proposal:
        proposal = self.inspect(proposal_id)
        if proposal.status not in {"STAGED", "EVALUATION_FAILED"}:
            raise GovernanceError(f"proposal cannot be evaluated from {proposal.status}")
        staged = Path(proposal.staged_path)
        if package_digest(staged) != proposal.staged_digest:
            raise GovernanceError("staged package digest changed before evaluation")

        records: list[EvaluationRecord] = []
        for name, evaluator in (
            ("structural", structural),
            ("semantic", semantic),
            ("integration", integration),
        ):
            try:
                outcome = evaluator(staged)
                if isinstance(outcome, tuple):
                    passed, detail = bool(outcome[0]), str(outcome[1])
                else:
                    passed, detail = bool(outcome), "passed" if outcome else "failed"
            except Exception as exc:
                passed, detail = False, f"{type(exc).__name__}: {exc}"
            records.append(EvaluationRecord(name, passed, detail, utc_now()))
            if not passed:
                failed = replace(
                    proposal,
                    status="EVALUATION_FAILED",
                    evaluations=tuple(records),
                )
                self._write_proposal(failed)
                raise GovernanceError(f"{name} evaluation failed: {detail}")
        evaluated = replace(
            proposal, status="EVALUATED", evaluations=tuple(records)
        )
        self._write_proposal(evaluated)
        return evaluated

    def approve(
        self, proposal_id: str, *, approved_by: str, confirmed: bool
    ) -> Approval:
        if not confirmed:
            raise GovernanceError("approval requires explicit confirmation")
        if not approved_by.strip():
            raise GovernanceError("approver identity is required")
        proposal = self.inspect(proposal_id)
        if proposal.status != "EVALUATED" or len(proposal.evaluations) != 3:
            raise GovernanceError("all staged evaluations must pass before approval")
        if not all(item.passed for item in proposal.evaluations):
            raise GovernanceError("failed evaluations cannot be approved")
        fields = {
            "proposal_id": proposal.proposal_id,
            "target_skill": proposal.target_skill,
            "source_digest": proposal.source_digest,
            "staged_digest": proposal.staged_digest,
            "approved_by": approved_by.strip(),
            "approved_at": utc_now(),
        }
        approval = Approval(
            approval_id=f"approval-{uuid.uuid4().hex[:16]}",
            proposal_id=proposal.proposal_id,
            target_skill=proposal.target_skill,
            source_digest=proposal.source_digest,
            staged_digest=proposal.staged_digest,
            approved_by=approved_by.strip(),
            approved_at=str(fields["approved_at"]),
            binding_digest=binding_digest(fields),
        )
        atomic_write_json(
            self._proposal_directory(proposal_id) / "approval.json",
            approval.to_dict(),
        )
        self._write_proposal(replace(proposal, status="APPROVED"))
        return approval

    def apply(
        self,
        approval: Approval,
        *,
        fault_injector: FaultInjector | None = None,
    ) -> Proposal:
        proposal = self.inspect(approval.proposal_id)
        self._verify_approval(proposal, approval)
        live = self._live_skill(proposal.target_skill)
        staged = Path(proposal.staged_path)
        journal_path = self._journal_path(proposal.proposal_id)
        lock_path = self.locks / f"{proposal.target_skill}.apply.lock"

        with OwnedFileLock(lock_path):
            if package_digest(live) != proposal.source_digest:
                raise GovernanceError("live package drifted after approval")
            if package_digest(staged) != proposal.staged_digest:
                raise GovernanceError("staged package drifted after approval")

            backup = self.backups / proposal.proposal_id / proposal.source_digest
            if backup.exists():
                if package_digest(backup) != proposal.source_digest:
                    raise GovernanceError("existing backup digest is invalid")
            else:
                backup.parent.mkdir(parents=True, exist_ok=True)
                copy_package(live, backup)
            journal = {
                "schema_version": 1,
                "proposal_id": proposal.proposal_id,
                "target_skill": proposal.target_skill,
                "source_digest": proposal.source_digest,
                "staged_digest": proposal.staged_digest,
                "live_path": str(live),
                "backup_path": str(backup),
                "old_path": str(
                    live.with_name(f".{live.name}.{proposal.proposal_id}.old")
                ),
                "candidate_path": str(
                    live.with_name(f".{live.name}.{proposal.proposal_id}.new")
                ),
                "phase": "BACKUP_COMPLETE",
                "updated_at": utc_now(),
            }
            self._write_journal(journal_path, journal)
            self._inject(fault_injector, "BACKUP_COMPLETE")

            old = Path(str(journal["old_path"]))
            candidate = Path(str(journal["candidate_path"]))
            remove_tree(old)
            remove_tree(candidate)
            copy_package(staged, candidate)
            try:
                atomic_replace(live, old)
                journal = self._advance(journal_path, journal, "LIVE_MOVED")
                self._inject(fault_injector, "LIVE_MOVED")
                atomic_replace(candidate, live)
                journal = self._advance(journal_path, journal, "SWAPPED")
                self._inject(fault_injector, "SWAPPED")
                final_digest = package_digest(live)
                if final_digest != proposal.staged_digest:
                    raise GovernanceError("survival verification failed after package swap")
                applied = replace(
                    proposal, status="APPLIED", final_digest=final_digest
                )
                self._write_proposal(applied)
                journal["final_digest"] = final_digest
                journal = self._advance(journal_path, journal, "COMMITTED")
                remove_tree(old)
                return applied
            except Exception:
                self._recover_journal_locked(
                    journal_path,
                    read_json(journal_path),
                    prefer_rollback=True,
                )
                raise

    def rollback(self, proposal_id: str, *, confirmed: bool) -> Proposal:
        if not confirmed:
            raise GovernanceError("rollback requires explicit confirmation")
        proposal = self.inspect(proposal_id)
        if proposal.status != "APPLIED":
            raise GovernanceError("only an applied proposal can be rolled back")
        backup = self.backups / proposal_id / proposal.source_digest
        if not backup.exists() or package_digest(backup) != proposal.source_digest:
            raise GovernanceError("complete verified backup is unavailable")
        live = self._live_skill(proposal.target_skill)
        lock_path = self.locks / f"{proposal.target_skill}.apply.lock"
        with OwnedFileLock(lock_path):
            candidate = live.with_name(f".{live.name}.{proposal_id}.rollback-new")
            replaced = live.with_name(f".{live.name}.{proposal_id}.rollback-old")
            remove_tree(candidate)
            remove_tree(replaced)
            copy_package(backup, candidate)
            atomic_replace(live, replaced)
            try:
                atomic_replace(candidate, live)
                if package_digest(live) != proposal.source_digest:
                    raise GovernanceError("rollback survival verification failed")
            except Exception:
                failed = live.with_name(f".{live.name}.{proposal_id}.rollback-failed")
                remove_tree(failed)
                if live.exists():
                    atomic_replace(live, failed)
                if replaced.exists():
                    atomic_replace(replaced, live)
                remove_tree(failed)
                remove_tree(candidate)
                raise
            remove_tree(replaced)
            rolled_back = replace(
                proposal, status="ROLLED_BACK", final_digest=proposal.source_digest
            )
            self._write_proposal(rolled_back)
            journal = read_json(self._journal_path(proposal_id))
            self._advance(
                self._journal_path(proposal_id), journal, "ROLLED_BACK"
            )
            return rolled_back

    def recover_interrupted(self) -> list[str]:
        recovered: list[str] = []
        for journal_path in sorted(self.journals.glob("proposal-*.json")):
            journal = read_json(journal_path)
            if journal.get("phase") in {"COMMITTED", "ROLLED_BACK", "RECOVERED"}:
                continue
            self._recover_journal(journal_path, prefer_rollback=True)
            recovered.append(str(journal["proposal_id"]))
        return recovered

    def inspect(self, proposal_id: str) -> Proposal:
        self._validate_proposal_id(proposal_id)
        path = self._proposal_directory(proposal_id) / "proposal.json"
        if not path.is_file():
            raise GovernanceError(f"unknown proposal: {proposal_id}")
        return Proposal.from_dict(read_json(path))

    def _recover_journal(self, journal_path: Path, *, prefer_rollback: bool) -> None:
        journal = read_json(journal_path)
        target_skill = str(journal["target_skill"])
        lock_path = self.locks / f"{target_skill}.apply.lock"
        with OwnedFileLock(lock_path):
            self._recover_journal_locked(
                journal_path,
                journal,
                prefer_rollback=prefer_rollback,
            )

    def _recover_journal_locked(
        self,
        journal_path: Path,
        journal: dict[str, object],
        *,
        prefer_rollback: bool,
    ) -> None:
        live = Path(str(journal["live_path"]))
        old = Path(str(journal["old_path"]))
        candidate = Path(str(journal["candidate_path"]))
        backup = Path(str(journal["backup_path"]))
        source_digest = str(journal["source_digest"])
        staged_digest = str(journal["staged_digest"])

        if not prefer_rollback and live.exists() and package_digest(live) == staged_digest:
            self._advance(journal_path, journal, "COMMITTED")
            remove_tree(old)
            remove_tree(candidate)
            return

        replacement = old if old.exists() else backup
        if not replacement.exists() or package_digest(replacement) != source_digest:
            raise GovernanceError(
                f"cannot recover interrupted proposal {journal['proposal_id']}"
            )
        failed = live.with_name(f".{live.name}.{journal['proposal_id']}.failed")
        remove_tree(failed)
        if live.exists():
            atomic_replace(live, failed)
        if replacement == old:
            atomic_replace(old, live)
        else:
            copy_package(backup, live)
        if package_digest(live) != source_digest:
            raise GovernanceError("recovery survival verification failed")
        remove_tree(failed)
        remove_tree(candidate)
        self._advance(journal_path, journal, "RECOVERED")
        proposal = self.inspect(str(journal["proposal_id"]))
        self._write_proposal(
            replace(
                proposal,
                status="RECOVERED",
                final_digest=source_digest,
            )
        )

    def _verify_approval(self, proposal: Proposal, supplied: Approval) -> None:
        path = self._proposal_directory(proposal.proposal_id) / "approval.json"
        if not path.is_file():
            raise GovernanceError("stored approval is missing")
        stored = Approval.from_dict(read_json(path))
        if stored != supplied:
            raise GovernanceError("supplied approval does not match the stored approval")
        fields = {
            "proposal_id": stored.proposal_id,
            "target_skill": stored.target_skill,
            "source_digest": stored.source_digest,
            "staged_digest": stored.staged_digest,
            "approved_by": stored.approved_by,
            "approved_at": stored.approved_at,
        }
        if stored.binding_digest != binding_digest(fields):
            raise GovernanceError("approval binding digest is invalid")
        if proposal.status != "APPROVED":
            raise GovernanceError(f"proposal is not approved: {proposal.status}")
        if (
            stored.target_skill != proposal.target_skill
            or stored.source_digest != proposal.source_digest
            or stored.staged_digest != proposal.staged_digest
        ):
            raise GovernanceError("approval is not bound to the exact proposal state")

    def _validate_proposal_inputs(self, **values: object) -> None:
        proposal_id = str(values["proposal_id"])
        target_skill = str(values["target_skill"])
        source_digest = str(values["source_digest"])
        evidence_ids = values["evidence_ids"]
        self._validate_proposal_id(proposal_id)
        if not SAFE_IDENTIFIER.fullmatch(target_skill):
            raise GovernanceError("unsafe target skill")
        if not SHA256.fullmatch(source_digest):
            raise GovernanceError("source digest must be a SHA-256 value")
        if not isinstance(evidence_ids, list) or not evidence_ids:
            raise GovernanceError("at least one evidence ID is required")
        if any(not isinstance(item, str) or not item.strip() for item in evidence_ids):
            raise GovernanceError("evidence IDs cannot be empty")
        for field in (
            "expected_benefit",
            "risk_analysis",
            "creator",
            "evaluation_plan",
        ):
            if not str(values[field]).strip():
                raise GovernanceError(f"{field} is required")

    def _validate_proposal_id(self, proposal_id: str) -> None:
        if not SAFE_PROPOSAL_ID.fullmatch(proposal_id):
            raise GovernanceError(f"unsafe proposal ID: {proposal_id}")

    def _live_skill(self, target_skill: str) -> Path:
        if not SAFE_IDENTIFIER.fullmatch(target_skill):
            raise GovernanceError("unsafe target skill")
        skills_root = self.repository_root / "skills"
        candidate = ensure_relative_to(skills_root, skills_root / target_skill)
        if not candidate.is_dir():
            raise GovernanceError(f"unknown target skill: {target_skill}")
        return candidate

    def _proposal_directory(self, proposal_id: str) -> Path:
        self._validate_proposal_id(proposal_id)
        return ensure_relative_to(self.proposals, self.proposals / proposal_id)

    def _write_proposal(self, proposal: Proposal) -> None:
        atomic_write_json(
            self._proposal_directory(proposal.proposal_id) / "proposal.json",
            proposal.to_dict(),
        )

    def _journal_path(self, proposal_id: str) -> Path:
        self._validate_proposal_id(proposal_id)
        return ensure_relative_to(self.journals, self.journals / f"{proposal_id}.json")

    @staticmethod
    def _write_journal(path: Path, journal: dict[str, object]) -> None:
        atomic_write_json(path, journal)

    def _advance(
        self, path: Path, journal: dict[str, object], phase: str
    ) -> dict[str, object]:
        updated = dict(journal)
        updated["phase"] = phase
        updated["updated_at"] = utc_now()
        self._write_journal(path, updated)
        return updated

    @staticmethod
    def _inject(injector: FaultInjector | None, phase: str) -> None:
        if injector is not None:
            injector(phase)
