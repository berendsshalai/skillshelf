from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest

from skillshelf_agents.governance import Approval, GovernanceError, GovernanceManager
from skillshelf_agents.governance.safety import SafetyError, package_digest


def _write_package(path: Path, *, marker: str = "original") -> None:
    path.mkdir(parents=True)
    for directory in ("references", "scripts", "assets", "tests"):
        (path / directory).mkdir()
    (path / "SKILL.md").write_text(
        "# Demo\n\nRead references/rules.md before acting.\n",
        encoding="utf-8",
    )
    (path / "README.md").write_text(f"demo package: {marker}\n", encoding="utf-8")
    (path / "PROVENANCE.yml").write_text("origin: test\n", encoding="utf-8")
    (path / "SEMANTIC_CONTRACT.yml").write_text(
        "contract: stable\n", encoding="utf-8"
    )
    (path / "UPSTREAM_DIFF.md").write_text("No upstream diff.\n", encoding="utf-8")
    (path / "references" / "rules.md").write_text(
        "Preserve complete packages.\n", encoding="utf-8"
    )
    (path / "scripts" / "check.py").write_text(
        "print('checked')\n", encoding="utf-8"
    )
    (path / "assets" / "marker.txt").write_text(marker, encoding="utf-8")
    (path / "tests" / "test_marker.txt").write_text(marker, encoding="utf-8")


@pytest.fixture
def manager(tmp_path: Path) -> GovernanceManager:
    repository = tmp_path / "repository"
    _write_package(repository / "skills" / "demo")
    return GovernanceManager(tmp_path / "home", repository)


def _stage(
    manager: GovernanceManager,
    proposal_id: str = "proposal-safe001",
) -> tuple[str, str]:
    source_digest = manager.source_digest("demo")

    def mutate(package: Path) -> None:
        (package / "README.md").write_text(
            "demo package: improved\n", encoding="utf-8"
        )
        (package / "references" / "rules.md").write_text(
            "Preserve complete packages and verify recovery.\n",
            encoding="utf-8",
        )

    proposal = manager.stage(
        proposal_id=proposal_id,
        target_skill="demo",
        source_digest=source_digest,
        evidence_ids=["eval-001"],
        expected_benefit="Safer package replacement",
        risk_analysis="Package swap can be interrupted",
        creator="test-suite",
        evaluation_plan="Run structural, semantic, and integration checks",
        mutate=mutate,
    )
    return source_digest, proposal.staged_digest


def _approve(manager: GovernanceManager, proposal_id: str) -> Approval:
    manager.evaluate(
        proposal_id,
        structural=lambda _: (True, "structure valid"),
        semantic=lambda _: (True, "semantics preserved"),
        integration=lambda _: (True, "integration passed"),
    )
    return manager.approve(
        proposal_id, approved_by="test-approver", confirmed=True
    )


@pytest.mark.parametrize(
    "proposal_id",
    ["../escape", "proposal-../../escape", "PROPOSAL-unsafe", "proposal-short"],
)
def test_rejects_unsafe_proposal_ids(
    manager: GovernanceManager, proposal_id: str
) -> None:
    with pytest.raises(GovernanceError, match="unsafe proposal ID"):
        manager.stage(
            proposal_id=proposal_id,
            target_skill="demo",
            source_digest=manager.source_digest("demo"),
            evidence_ids=["eval-001"],
            expected_benefit="benefit",
            risk_analysis="risk",
            creator="creator",
            evaluation_plan="plan",
            mutate=lambda _: None,
        )


def test_rejects_unknown_targets_and_empty_evidence(
    manager: GovernanceManager,
) -> None:
    digest = manager.source_digest("demo")
    with pytest.raises(GovernanceError, match="unknown target"):
        manager.stage(
            proposal_id="proposal-unknown1",
            target_skill="missing",
            source_digest=digest,
            evidence_ids=["eval-001"],
            expected_benefit="benefit",
            risk_analysis="risk",
            creator="creator",
            evaluation_plan="plan",
            mutate=lambda _: None,
        )
    with pytest.raises(GovernanceError, match="at least one evidence"):
        manager.stage(
            proposal_id="proposal-noevidence",
            target_skill="demo",
            source_digest=digest,
            evidence_ids=[],
            expected_benefit="benefit",
            risk_analysis="risk",
            creator="creator",
            evaluation_plan="plan",
            mutate=lambda _: None,
        )


def test_rejects_source_drift_at_staging_and_apply(
    manager: GovernanceManager,
) -> None:
    stale = manager.source_digest("demo")
    live = Path(manager.repository_root) / "skills" / "demo"
    (live / "README.md").write_text("external drift\n", encoding="utf-8")
    with pytest.raises(GovernanceError, match="expected source digest"):
        manager.stage(
            proposal_id="proposal-driftstage",
            target_skill="demo",
            source_digest=stale,
            evidence_ids=["eval-001"],
            expected_benefit="benefit",
            risk_analysis="risk",
            creator="creator",
            evaluation_plan="plan",
            mutate=lambda _: None,
        )

    _stage(manager, "proposal-driftapply")
    approval = _approve(manager, "proposal-driftapply")
    (live / "README.md").write_text("post-approval drift\n", encoding="utf-8")
    drifted_digest = package_digest(live)
    with pytest.raises(GovernanceError, match="drifted after approval"):
        manager.apply(approval)
    assert package_digest(live) == drifted_digest
    assert not (manager.backups / "proposal-driftapply").exists()


def test_evaluators_run_in_required_order_before_live_mutation(
    manager: GovernanceManager,
) -> None:
    source_digest, _ = _stage(manager, "proposal-evalorder")
    observed: list[str] = []
    live = Path(manager.repository_root) / "skills" / "demo"

    def check(name: str) -> tuple[bool, str]:
        observed.append(name)
        assert package_digest(live) == source_digest
        return True, f"{name} passed"

    evaluated = manager.evaluate(
        "proposal-evalorder",
        structural=lambda _: check("structural"),
        semantic=lambda _: check("semantic"),
        integration=lambda _: check("integration"),
    )
    assert observed == ["structural", "semantic", "integration"]
    assert [record.name for record in evaluated.evaluations] == observed
    assert package_digest(live) == source_digest


def test_evaluation_stops_on_first_failure_without_mutating_live(
    manager: GovernanceManager,
) -> None:
    source_digest, _ = _stage(manager, "proposal-evalfail")
    observed: list[str] = []

    def structural(_: Path) -> bool:
        observed.append("structural")
        return False

    with pytest.raises(GovernanceError, match="structural evaluation failed"):
        manager.evaluate(
            "proposal-evalfail",
            structural=structural,
            semantic=lambda _: observed.append("semantic") is None,
            integration=lambda _: observed.append("integration") is None,
        )
    assert observed == ["structural"]
    assert manager.source_digest("demo") == source_digest
    assert manager.inspect("proposal-evalfail").status == "EVALUATION_FAILED"


def test_apply_requires_exact_stored_approval_binding(
    manager: GovernanceManager,
) -> None:
    _stage(manager, "proposal-binding")
    approval = _approve(manager, "proposal-binding")
    forged = replace(approval, staged_digest="0" * 64)
    with pytest.raises(GovernanceError, match="does not match"):
        manager.apply(forged)
    assert manager.inspect("proposal-binding").status == "APPROVED"


@pytest.mark.parametrize("phase", ["LIVE_MOVED", "SWAPPED"])
def test_injected_swap_failure_recovers_original_package(
    manager: GovernanceManager, phase: str
) -> None:
    proposal_id = f"proposal-fail{phase.lower().replace('_', '')}"
    source_digest, _ = _stage(manager, proposal_id)
    approval = _approve(manager, proposal_id)

    def fail_at(observed_phase: str) -> None:
        if observed_phase == phase:
            raise RuntimeError(f"injected at {phase}")

    with pytest.raises(RuntimeError, match="injected"):
        manager.apply(approval, fault_injector=fail_at)

    assert manager.source_digest("demo") == source_digest
    assert manager.inspect(proposal_id).status == "RECOVERED"
    journal = json.loads(
        (manager.journals / f"{proposal_id}.json").read_text(encoding="utf-8")
    )
    assert journal["phase"] == "RECOVERED"
    assert not Path(str(journal["old_path"])).exists()
    assert not Path(str(journal["candidate_path"])).exists()


def test_recover_interrupted_backup_phase_is_idempotent(
    manager: GovernanceManager,
) -> None:
    proposal_id = "proposal-backupfail"
    source_digest, _ = _stage(manager, proposal_id)
    approval = _approve(manager, proposal_id)

    def fail_at_backup(phase: str) -> None:
        if phase == "BACKUP_COMPLETE":
            raise RuntimeError("power loss after backup")

    with pytest.raises(RuntimeError, match="power loss"):
        manager.apply(approval, fault_injector=fail_at_backup)
    assert manager.recover_interrupted() == [proposal_id]
    assert manager.recover_interrupted() == []
    assert manager.source_digest("demo") == source_digest
    assert manager.inspect(proposal_id).status == "RECOVERED"


def test_successful_apply_preserves_complete_backup_and_can_rollback(
    manager: GovernanceManager,
) -> None:
    proposal_id = "proposal-success1"
    source_digest, staged_digest = _stage(manager, proposal_id)
    approval = _approve(manager, proposal_id)

    applied = manager.apply(approval)
    live = Path(manager.repository_root) / "skills" / "demo"
    backup = manager.backups / proposal_id / source_digest
    assert applied.status == "APPLIED"
    assert applied.final_digest == staged_digest
    assert package_digest(live) == staged_digest
    assert package_digest(backup) == source_digest
    assert (backup / "references" / "rules.md").is_file()
    assert (backup / "scripts" / "check.py").is_file()
    assert (backup / "assets" / "marker.txt").is_file()
    assert (backup / "tests" / "test_marker.txt").is_file()

    rolled_back = manager.rollback(proposal_id, confirmed=True)
    assert rolled_back.status == "ROLLED_BACK"
    assert rolled_back.final_digest == source_digest
    assert package_digest(live) == source_digest
    journal = json.loads(
        (manager.journals / f"{proposal_id}.json").read_text(encoding="utf-8")
    )
    assert journal["phase"] == "ROLLED_BACK"


def test_stage_rejects_missing_skill_reference_and_removes_partial_state(
    manager: GovernanceManager,
) -> None:
    proposal_id = "proposal-missingref"

    def remove_reference(package: Path) -> None:
        (package / "references" / "rules.md").unlink()

    with pytest.raises(SafetyError, match="missing referenced files"):
        manager.stage(
            proposal_id=proposal_id,
            target_skill="demo",
            source_digest=manager.source_digest("demo"),
            evidence_ids=["eval-001"],
            expected_benefit="benefit",
            risk_analysis="risk",
            creator="creator",
            evaluation_plan="plan",
            mutate=remove_reference,
        )
    assert not (manager.proposals / proposal_id).exists()
