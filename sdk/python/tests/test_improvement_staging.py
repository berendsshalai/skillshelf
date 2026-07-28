import pytest
from concurrent.futures import ThreadPoolExecutor

from skillshelf_agents.contracts import Observation
from skillshelf_agents.event_log import EventLog

from skillshelf_agents.improvement import ProposalStore


def test_staging_does_not_mutate_live_and_rollback_works(tmp_path):
    root = tmp_path / "repo"
    skill = root / "skills/demo/SKILL.md"
    skill.parent.mkdir(parents=True)
    skill.write_text("live")
    store = ProposalStore(tmp_path / "home", root)
    proposal = store.stage("demo", "staged", ["event-1"])
    assert skill.read_text() == "live"
    with pytest.raises(RuntimeError):
        store.approve(proposal, confirmed=True, evaluator=lambda _: False)
    assert skill.read_text() == "live"
    assert store.inspect(proposal)["status"] == "rolled-back"


def test_approval_and_rejection_require_explicit_flow(tmp_path):
    root = tmp_path / "repo"
    skill = root / "skills/demo/SKILL.md"
    skill.parent.mkdir(parents=True)
    skill.write_text("live")
    store = ProposalStore(tmp_path / "home", root)
    proposal = store.stage("demo", "new", [])
    with pytest.raises(ValueError):
        store.approve(proposal, confirmed=False, evaluator=lambda _: True)
    store.reject(proposal)
    assert store.inspect(proposal)["status"] == "rejected"


def test_concurrent_observation_writes_are_serialised(tmp_path):
    log = EventLog(tmp_path / "events")

    def append(index):
        log.append(Observation(
            run_id=str(index), timestamp="2026-07-28T00:00:00Z", agents_used=[], skills_used=[],
            routing_decision={}, usage={}, tool_failures=[], guardrail_events=[], user_corrections=[],
            evaluation_failures=[],
        ))

    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(append, range(24)))
    assert len(log.read()) == 24
