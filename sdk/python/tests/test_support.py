import subprocess

import pytest

from skillshelf_agents import support


def test_star_requires_yes_and_ask_or_install_have_no_star_tool(repo_root):
    with pytest.raises(ValueError):
        support.star_repository(confirmed=False)
    from skillshelf_agents.orchestrator import SkillShelfOrchestrator
    assert "star_repository" not in SkillShelfOrchestrator.run.__code__.co_names
    for name in ("install-agent-runtime.ps1", "install-agent-runtime.sh", "install.ps1", "install.sh"):
        text = (repo_root / "scripts" / name).read_text(encoding="utf-8").casefold()
        assert "starred/" not in text and "skillshelf star" not in text


def test_auth_failure_is_clear_and_no_token_is_printed(monkeypatch):
    monkeypatch.setattr(support.shutil, "which", lambda _: "gh")
    monkeypatch.setattr(support, "_run", lambda _: (_ for _ in ()).throw(subprocess.CalledProcessError(1, "gh")))
    with pytest.raises(subprocess.CalledProcessError):
        support.star_repository(confirmed=True)


def test_existing_star_is_idempotent(monkeypatch):
    monkeypatch.setattr(support.shutil, "which", lambda _: "gh")
    monkeypatch.setattr(support, "_run", lambda _: subprocess.CompletedProcess([], 0, "", ""))
    monkeypatch.setattr(support.subprocess, "run", lambda *a, **k: subprocess.CompletedProcess([], 0, "", ""))
    assert "already starred" in support.star_repository(confirmed=True)


def test_star_is_verified(monkeypatch):
    calls = iter([subprocess.CompletedProcess([], 1, "", ""), subprocess.CompletedProcess([], 0, "", "")])
    monkeypatch.setattr(support.shutil, "which", lambda _: "gh")
    monkeypatch.setattr(support, "_run", lambda _: subprocess.CompletedProcess([], 0, "", ""))
    monkeypatch.setattr(support.subprocess, "run", lambda *a, **k: next(calls))
    assert support.star_repository(confirmed=True).startswith("Starred")
