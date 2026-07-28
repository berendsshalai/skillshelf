from __future__ import annotations

import asyncio
import json
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

import typer
from rich.console import Console

from .agent_factory import AgentFactory
from .budgets import UsageStore
from .config import Settings, find_repository
from .improvement import ProposalStore
from .mcp_runtime import MCPRuntime
from .orchestrator import SkillShelfOrchestrator
from .registry import RuntimeRegistry
from .routing import route_task
from .sessions import SessionStore
from .skill_loader import SkillLoader
from .support import star_repository

app = typer.Typer(help="SkillShelf Codex-first agent runtime", no_args_is_help=True)
agents_app = typer.Typer(help="Inspect specialist agents")
usage_app = typer.Typer(help="Inspect local token usage", invoke_without_command=True)
sessions_app = typer.Typer(help="Manage SDK conversational sessions", invoke_without_command=True)
mcp_app = typer.Typer(help="Inspect MCP policy", invoke_without_command=True)
proposals_app = typer.Typer(help="Inspect and approve staged improvements", invoke_without_command=True)
app.add_typer(agents_app, name="agents")
app.add_typer(usage_app, name="usage")
app.add_typer(sessions_app, name="sessions")
app.add_typer(mcp_app, name="mcp")
app.add_typer(proposals_app, name="proposals")
console = Console()


def _runtime() -> tuple[Path, Settings, RuntimeRegistry]:
    root = find_repository()
    settings = Settings()
    settings.initialise()
    return root, settings, RuntimeRegistry.load(root)


def _emit(value: Any, as_json: bool) -> None:
    if as_json:
        console.print_json(json.dumps(value, default=str))
    else:
        console.print(value)


@app.command()
def ask(task: str, session: str = "default", json_output: bool = typer.Option(False, "--json")) -> None:
    """Route a task through the master or a high-confidence specialist."""
    root, settings, registry = _runtime()
    runtime = SkillShelfOrchestrator(registry, AgentFactory(registry, SkillLoader(root)), settings)
    try:
        output = asyncio.run(runtime.run(task, session_id=session))
    except Exception as exc:
        _emit({"status": "error", "error": str(exc)}, json_output)
        raise typer.Exit(2) from exc
    _emit(output.model_dump(), json_output)


@app.command("run")
def run_agent(agent: str = typer.Option(..., "--agent"), task: str = typer.Argument(...),
              session: str = "default", json_output: bool = typer.Option(False, "--json")) -> None:
    root, settings, registry = _runtime()
    registry.by_id(agent)
    runtime = SkillShelfOrchestrator(registry, AgentFactory(registry, SkillLoader(root)), settings)
    try:
        output = asyncio.run(runtime.run(task, session_id=session, explicit_agent=agent))
    except Exception as exc:
        _emit({"status": "error", "error": str(exc)}, json_output)
        raise typer.Exit(2) from exc
    _emit(output.model_dump(), json_output)


@agents_app.callback(invoke_without_command=True)
def list_agents(ctx: typer.Context, json_output: bool = typer.Option(False, "--json")) -> None:
    if ctx.invoked_subcommand:
        return
    _, _, registry = _runtime()
    rows = [{"id": item.id, "skill": item.skill, "model_profile": item.model_profile,
             "mcp": item.allowed_mcp} for item in registry.agents]
    _emit(rows, json_output)


@agents_app.command("inspect")
def inspect_agent(agent_id: str, json_output: bool = typer.Option(False, "--json")) -> None:
    _, _, registry = _runtime()
    _emit(registry.by_id(agent_id).model_dump(), json_output)


@app.command()
def doctor(json_output: bool = typer.Option(False, "--json")) -> None:
    checks: list[dict[str, str]] = []
    try:
        root, settings, registry = _runtime()
        checks.append({"check": "registry", "status": "PASS"})
        generated = root / "agents" / "generated" / "codex"
        checks.append({"check": "generated agents", "status": "PASS" if len(list(generated.glob("*.toml"))) == 6 else "FAIL"})
        checks.append({"check": "API configuration", "status": "PASS" if os.getenv("OPENAI_API_KEY") else "WARNING"})
        checks.append({"check": "Python", "status": "PASS", "detail": platform.python_version()})
        checks.append({"check": "write permissions", "status": "PASS" if os.access(settings.home, os.W_OK) else "FAIL"})
        checks.append({"check": "GitHub CLI", "status": "PASS" if shutil.which("gh") else "WARNING"})
        checks.append({"check": "MCP policy", "status": "PASS" if MCPRuntime(root).servers else "FAIL"})
        checks.append({"check": "memory worker", "status": "SKIPPED"})
        checks.append({"check": "tracing sensitive data", "status": "PASS" if not settings.trace_include_sensitive else "WARNING"})
        checks.append({"check": "auto review", "status": "PASS" if not settings.auto_review else "WARNING"})
        checks.append({"check": "model profiles", "status": "PASS", "detail": settings.model})
        SessionStore(settings.home / "sessions" / "sessions.sqlite")
        checks.append({"check": "session database", "status": "PASS"})
        del registry
    except Exception as exc:
        checks.append({"check": "startup", "status": "FAIL", "detail": str(exc)})
    _emit(checks, json_output)
    if any(item["status"] == "FAIL" for item in checks):
        raise typer.Exit(1)


@usage_app.callback(invoke_without_command=True)
def usage(ctx: typer.Context, last: bool = False, session: str | None = None, agent: str | None = None,
          json_output: bool = typer.Option(False, "--json")) -> None:
    if ctx.invoked_subcommand:
        return
    _, settings, _ = _runtime()
    records = UsageStore(settings.home / "usage").query(session=session, agent=agent)
    if last:
        records = records[-1:]
    _emit(records, json_output)


@sessions_app.callback(invoke_without_command=True)
def sessions_list(ctx: typer.Context, json_output: bool = typer.Option(False, "--json")) -> None:
    if ctx.invoked_subcommand:
        return
    _, settings, _ = _runtime()
    _emit(SessionStore(settings.home / "sessions" / "sessions.sqlite").list(), json_output)


@sessions_app.command("list")
def sessions_list_command(json_output: bool = typer.Option(False, "--json")) -> None:
    _, settings, _ = _runtime()
    _emit(SessionStore(settings.home / "sessions" / "sessions.sqlite").list(), json_output)


def _sessions() -> SessionStore:
    _, settings, _ = _runtime()
    return SessionStore(settings.home / "sessions" / "sessions.sqlite")


@sessions_app.command("inspect")
def session_inspect(session_id: str) -> None:
    _emit(_sessions().inspect(session_id), False)


@sessions_app.command("delete")
def session_delete(session_id: str, yes: bool = typer.Option(False, "--yes")) -> None:
    _sessions().delete(session_id, confirmed=yes)


@sessions_app.command("export")
def session_export(session_id: str, destination: Path) -> None:
    console.print(_sessions().export(session_id, destination))


@mcp_app.callback(invoke_without_command=True)
def mcp_list(ctx: typer.Context, json_output: bool = typer.Option(False, "--json")) -> None:
    if ctx.invoked_subcommand:
        return
    root, _, _ = _runtime()
    _emit(sorted(MCPRuntime(root).servers), json_output)


@mcp_app.command("list")
def mcp_list_command(json_output: bool = typer.Option(False, "--json")) -> None:
    root, _, _ = _runtime()
    _emit(sorted(MCPRuntime(root).servers), json_output)


@mcp_app.command("doctor")
def mcp_doctor() -> None:
    root, _, _ = _runtime()
    _emit(MCPRuntime(root).health(), False)


@mcp_app.command("tools")
def mcp_tools(server: str) -> None:
    root, _, _ = _runtime()
    _emit(MCPRuntime(root).tools(server), False)


@mcp_app.command("permissions")
def mcp_permissions(agent: str) -> None:
    root, _, registry = _runtime()
    definition = registry.by_id(agent)
    _emit(MCPRuntime(root).permissions(definition.allowed_mcp), False)


@app.command()
def improve() -> None:
    _, settings, _ = _runtime()
    console.print(f"Auto-review is off. Observations: {len(list((settings.home / 'events').glob('*.jsonl')))}. "
                  "Use a reviewed proposal; live skills are never mutated automatically.")


@proposals_app.callback(invoke_without_command=True)
def proposals_list(ctx: typer.Context) -> None:
    if ctx.invoked_subcommand:
        return
    root, settings, _ = _runtime()
    _emit(ProposalStore(settings.home, root).list(), False)


@proposals_app.command("list")
def proposals_list_command(json_output: bool = typer.Option(False, "--json")) -> None:
    root, settings, _ = _runtime()
    _emit(ProposalStore(settings.home, root).list(), json_output)


@proposals_app.command("inspect")
def proposal_inspect(proposal_id: str) -> None:
    root, settings, _ = _runtime()
    _emit(ProposalStore(settings.home, root).inspect(proposal_id), False)


@proposals_app.command("reject")
def proposal_reject(proposal_id: str, yes: bool = typer.Option(False, "--yes")) -> None:
    if not yes:
        raise typer.BadParameter("rejection requires --yes")
    root, settings, _ = _runtime()
    ProposalStore(settings.home, root).reject(proposal_id)


@proposals_app.command("approve")
def proposal_approve(proposal_id: str, yes: bool = typer.Option(False, "--yes")) -> None:
    root, settings, _ = _runtime()
    def evaluator(_skill: str) -> bool:
        return subprocess.run([os.fspath(Path(sys.executable)), "-m", "pytest", "-q"], cwd=root).returncode == 0
    ProposalStore(settings.home, root).approve(proposal_id, confirmed=yes, evaluator=evaluator)


@app.command("support")
def support_command() -> None:
    root, _, _ = _runtime()
    console.print((root / "support" / "SUPPORT.md").read_text(encoding="utf-8"))


@app.command()
def star(yes: bool = typer.Option(False, "--yes")) -> None:
    try:
        console.print(star_repository(confirmed=yes))
    except Exception as exc:
        console.print(f"Star not performed: {exc}")
        raise typer.Exit(2) from exc


@app.command(hidden=True)
def route(task: str) -> None:
    _emit(route_task(task).model_dump(), True)
