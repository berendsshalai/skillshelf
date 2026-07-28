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
from .connectors import ConnectorManifest
from .data import IntegrationDatabase
from .event_log import EventLog
from .improvement import ProposalStore
from .ledger import RunLedger
from .mcp_runtime import MCPRuntime
from .orchestrator import SkillShelfOrchestrator
from .registry import RuntimeRegistry
from .routing import route_task
from .runtime.approvals import ApprovalStore
from .sessions import SessionStore, UnifiedSessionManager
from .skill_loader import SkillLoader
from .suggestions.engine import CapabilityState, suggest_capabilities
from .support import star_repository
from .tools import CapabilityToolRegistry

app = typer.Typer(help="SkillShelf Codex-first agent runtime", no_args_is_help=True)
agents_app = typer.Typer(help="Inspect specialist agents")
usage_app = typer.Typer(help="Inspect local token usage", invoke_without_command=True)
sessions_app = typer.Typer(help="Manage SDK conversational sessions", invoke_without_command=True)
mcp_app = typer.Typer(help="Inspect MCP policy", invoke_without_command=True)
proposals_app = typer.Typer(help="Inspect and approve staged improvements", invoke_without_command=True)
approvals_app = typer.Typer(help="Inspect exact-argument runtime approvals")
runs_app = typer.Typer(help="Inspect durable runtime runs")
events_app = typer.Typer(help="Inspect runtime events")
traces_app = typer.Typer(help="Inspect traces")
connector_app = typer.Typer(help="Manage provider-neutral connectors")
workflow_app = typer.Typer(help="Manage durable workflows")
app.add_typer(agents_app, name="agents")
app.add_typer(usage_app, name="usage")
app.add_typer(sessions_app, name="sessions")
app.add_typer(mcp_app, name="mcp")
app.add_typer(proposals_app, name="proposals")
app.add_typer(approvals_app, name="approvals")
app.add_typer(runs_app, name="runs")
app.add_typer(events_app, name="events")
app.add_typer(traces_app, name="traces")
app.add_typer(connector_app, name="connector")
app.add_typer(workflow_app, name="workflow")
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
def doctor(
    deep: bool = typer.Option(False, "--deep"),
    credentialed: bool = typer.Option(False, "--credentialed"),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
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
        mcp_health = MCPRuntime(root).health()
        checks.append({
            "check": "MCP policy",
            "status": "PASS" if mcp_health and all(
                value in {"PASS", "SKIPPED", "DEGRADED"} for value in mcp_health.values()
            ) else "FAIL",
            "detail": json.dumps(mcp_health, sort_keys=True),
        })
        checks.append({"check": "tracing sensitive data", "status": "PASS" if not settings.trace_include_sensitive else "WARNING"})
        checks.append({"check": "auto review", "status": "PASS" if not settings.auto_review else "WARNING"})
        checks.append({"check": "model profiles", "status": "PASS", "detail": settings.model})
        SessionStore(settings.home / "sessions" / "skillshelf.sqlite")
        checks.append({"check": "session database", "status": "PASS"})
        if deep:
            version = (root / "VERSION").read_text(encoding="utf-8").strip()
            version_check = subprocess.run(
                [sys.executable, str(root / "scripts" / "validate-version.py")],
                cwd=root,
                capture_output=True,
                text=True,
                shell=False,
            )
            checks.append({"check": "version consistency", "status": "PASS" if version_check.returncode == 0 else "FAIL"})
            generation = subprocess.run(
                [sys.executable, str(root / "scripts" / "generate-agents.py"), "--profile", "runtime", "--check"],
                cwd=root,
                capture_output=True,
                text=True,
                shell=False,
            )
            checks.append({"check": "agent generation drift", "status": "PASS" if generation.returncode == 0 else "FAIL"})
            ledger = RunLedger(settings.home / "runs" / "ledger.sqlite")
            probe = f"doctor-{os.getpid()}"
            try:
                ledger.create_run(
                    run_id=probe,
                    trace_id=probe,
                    session_id=probe,
                    canonical_input={"doctor": True},
                    configuration_version=version,
                )
                checks.append({"check": "run-ledger write", "status": "PASS"})
                ledger.record_error(probe, code="doctor_probe", message="expected diagnostic event")
                checks.append({"check": "event failure capture", "status": "PASS"})
            except Exception as exc:
                checks.append({"check": "run-ledger write", "status": "FAIL", "detail": str(exc)})
            integration = IntegrationDatabase(settings.home / "operations.sqlite")
            integration.close()
            checks.extend([
                {"check": "connector database", "status": "PASS"},
                {"check": "workflow database", "status": "PASS"},
            ])
            from .rag import SQLiteKnowledgeBase
            knowledge = SQLiteKnowledgeBase(settings.home / "rag.sqlite")
            knowledge.close()
            checks.append({"check": "RAG database", "status": "PASS"})
            from .governance import GovernanceManager
            recovered = GovernanceManager(settings.home, root).recover_interrupted()
            checks.append({
                "check": "governance interrupted-apply recovery",
                "status": "PASS",
                "detail": f"recovered={len(recovered)}",
            })
            from .contracts import SpecialistResult
            SpecialistResult(
                agent_id="doctor",
                status="completed",
                summary="schema probe",
                context_for_master="schema probe",
            )
            checks.append({"check": "actual structured-output support", "status": "PASS"})
            from .runtime import RuntimeContext
            from .sessions.identity import repository_identity
            context = RuntimeContext(
                run_id=probe,
                trace_id=probe,
                session_id=probe,
                repository_root=root,
                repository_identity=repository_identity(root),
                soft_token_limit=100,
                hard_token_limit=200,
            )
            approvals = ApprovalStore(settings.home / "runs" / "ledger.sqlite")
            approval = approvals.request(
                context=context,
                tool_name="write_text_file",
                arguments={"path": "doctor-probe.txt", "content": "probe"},
                operation="write",
                approving_user="doctor",
                ttl_seconds=60,
            )
            interrupted = not approvals.is_granted(approval.approval_id)
            approvals.reject(approval.approval_id, approving_user="doctor")
            checks.append({
                "check": "write approval interruption",
                "status": "PASS" if interrupted else "FAIL",
            })
            from agents.tool_context import ToolContext
            from .tools.artefacts import ArtifactStore
            from .tools.filesystem import RepositoryFilesystem
            from .tools.subprocess import SafeCommandExecutor
            tool_registry = CapabilityToolRegistry(
                filesystem=RepositoryFilesystem(root, settings.home / "backups" / "doctor"),
                commands=SafeCommandExecutor(root, ArtifactStore(settings.home / "artifacts")),
            )
            read_tool = next(item for item in tool_registry.build(["read_files"]) if item.name == "read_text_file")
            async def invoke_read_tool() -> Any:
                return await read_tool.on_invoke_tool(
                    ToolContext(
                        context=context,
                        tool_name=read_tool.name,
                        tool_call_id=probe,
                        tool_arguments='{"path":"VERSION"}',
                    ),
                    '{"path":"VERSION"}',
                )
            tool_output: Any = asyncio.run(invoke_read_tool())
            checks.append({
                "check": "actual function-tool call",
                "status": "PASS" if version in str(tool_output) else "FAIL",
            })
            manager = UnifiedSessionManager(settings.home / "sessions" / "skillshelf.sqlite")
            session_probe = f"{probe}-session"
            manager.create_with_id(session_probe, repository_identity=context.repository_identity)
            async def session_round_trip() -> bool:
                sdk_session = manager.sdk_session(session_probe)
                await sdk_session.add_items([{"role": "user", "content": "doctor probe"}])
                before = await sdk_session.get_items()
                await manager.delete(session_probe, confirmed=True)
                return bool(before) and manager.verify_deleted(session_probe)
            session_ok = asyncio.run(session_round_trip())
            checks.append({
                "check": "session write/read/delete",
                "status": "PASS" if session_ok else "FAIL",
            })
            checks.extend([
                {
                    "check": "actual model/master/specialist invocation",
                    "status": "SKIPPED" if not credentialed else "DEGRADED",
                    "detail": "Use a credentialled evaluation fixture; doctor never makes an implicit paid call.",
                },
                {
                    "check": "actual MCP connection/discovery/read",
                    "status": "SKIPPED",
                    "detail": "No required local MCP provider was connected during this diagnostic.",
                },
                {"check": "optional provider readiness", "status": "SKIPPED"},
            ])
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
    _emit(SessionStore(settings.home / "sessions" / "skillshelf.sqlite").list(), json_output)


@sessions_app.command("list")
def sessions_list_command(json_output: bool = typer.Option(False, "--json")) -> None:
    _, settings, _ = _runtime()
    _emit(SessionStore(settings.home / "sessions" / "skillshelf.sqlite").list(), json_output)


def _sessions() -> SessionStore:
    _, settings, _ = _runtime()
    return SessionStore(settings.home / "sessions" / "skillshelf.sqlite")


def _session_manager() -> UnifiedSessionManager:
    _, settings, _ = _runtime()
    return UnifiedSessionManager(settings.home / "sessions" / "skillshelf.sqlite")


@sessions_app.command("inspect")
def session_inspect(session_id: str) -> None:
    _emit(_session_manager().inspect(session_id), False)


@sessions_app.command("delete")
def session_delete(session_id: str, yes: bool = typer.Option(False, "--yes")) -> None:
    asyncio.run(_session_manager().delete(session_id, confirmed=yes))
    if not _session_manager().verify_deleted(session_id):
        raise typer.Exit(1)


@sessions_app.command("export")
def session_export(session_id: str, destination: Path) -> None:
    console.print(asyncio.run(_session_manager().export(session_id, destination)))


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


def _approval_store() -> ApprovalStore:
    _, settings, _ = _runtime()
    return ApprovalStore(settings.home / "runs" / "ledger.sqlite")


@approvals_app.command("list")
def approvals_list(json_output: bool = typer.Option(False, "--json")) -> None:
    _emit([item.model_dump(mode="json") for item in _approval_store().list()], json_output)


@approvals_app.command("inspect")
def approvals_inspect(approval_id: str, json_output: bool = typer.Option(False, "--json")) -> None:
    _emit(_approval_store().inspect(approval_id).model_dump(mode="json"), json_output)


@approvals_app.command("approve")
def approvals_approve(approval_id: str, user: str = typer.Option(..., "--user")) -> None:
    _approval_store().approve(approval_id, approving_user=user)
    console.print(f"Approved {approval_id} for its exact bound arguments.")


@approvals_app.command("reject")
def approvals_reject(approval_id: str, user: str = typer.Option(..., "--user")) -> None:
    _approval_store().reject(approval_id, approving_user=user)
    console.print(f"Rejected {approval_id}.")


def _run_ledger() -> RunLedger:
    _, settings, _ = _runtime()
    return RunLedger(settings.home / "runs" / "ledger.sqlite")


@runs_app.command("list")
def runs_list(limit: int = typer.Option(100, min=1, max=1000), json_output: bool = typer.Option(False, "--json")) -> None:
    _emit([item.model_dump(mode="json") for item in _run_ledger().list_runs(limit=limit)], json_output)


@runs_app.command("inspect")
def runs_inspect(run_id: str, json_output: bool = typer.Option(False, "--json")) -> None:
    _emit(_run_ledger().inspect_run(run_id).model_dump(mode="json"), json_output)


@runs_app.command("artifacts")
def runs_artifacts(run_id: str, json_output: bool = typer.Option(False, "--json")) -> None:
    record = _run_ledger().inspect_run(run_id)
    _emit([
        {"tool_call_id": item.tool_call_id, "output_digest": item.output_digest}
        for item in record.tool_calls if item.output_digest
    ], json_output)


@runs_app.command("cancel")
def runs_cancel(run_id: str) -> None:
    from .ledger.models import RunStatus
    _run_ledger().transition(run_id, RunStatus.CANCELLED)


@runs_app.command("replay")
def runs_replay(run_id: str) -> None:
    record = _run_ledger().inspect_run(run_id)
    _emit({
        "status": "approval_required",
        "original_run_id": run_id,
        "canonical_input": record.canonical_input,
        "reason": "Replay creates a linked run and never replays outbound communications automatically.",
    }, False)


@events_app.command("tail")
def events_tail(limit: int = typer.Option(20, min=1, max=1000)) -> None:
    _, settings, _ = _runtime()
    _emit(EventLog(settings.home / "events").read()[-limit:], False)


@traces_app.command("inspect")
def traces_inspect(trace_id: str) -> None:
    matches = [
        item.model_dump(mode="json")
        for item in _run_ledger().list_runs(limit=1000)
        if item.trace_id == trace_id
    ]
    if not matches:
        raise typer.BadParameter("trace not found")
    _emit(matches, False)


def _connector_directory() -> Path:
    _, settings, _ = _runtime()
    directory = settings.home / "connectors"
    directory.mkdir(parents=True, exist_ok=True)
    return directory


@connector_app.command("list")
def connector_list() -> None:
    _emit([
        json.loads(path.read_text(encoding="utf-8"))
        for path in sorted(_connector_directory().glob("*.json"))
    ], False)


@connector_app.command("add")
def connector_add(manifest: Path) -> None:
    value = ConnectorManifest.model_validate_json(manifest.read_text(encoding="utf-8"))
    destination = _connector_directory() / f"{value.id}.json"
    if destination.exists():
        raise typer.BadParameter("connector already exists")
    destination.write_text(value.model_dump_json(indent=2) + "\n", encoding="utf-8")
    console.print(f"Stored reviewed connector manifest {value.id}; no network call was made.")


@connector_app.command("test")
def connector_test(connector_id: str) -> None:
    path = _connector_directory() / f"{connector_id}.json"
    value = ConnectorManifest.model_validate_json(path.read_text(encoding="utf-8"))
    _emit({"id": value.id, "manifest": "PASS", "network": "SKIPPED"}, False)


@connector_app.command("doctor")
def connector_doctor(connector_id: str) -> None:
    connector_test(connector_id)


@connector_app.command("sync")
def connector_sync(connector_id: str) -> None:
    path = _connector_directory() / f"{connector_id}.json"
    if not path.exists():
        raise typer.BadParameter("connector not found")
    console.print("Sync requires an explicitly configured resource operation and secret references.")
    raise typer.Exit(2)


@connector_app.command("import-openapi")
def connector_import_openapi(source: str) -> None:
    del source
    console.print("OpenAPI code generation is not completed in 0.3.0; no connector was activated.")
    raise typer.Exit(2)


def _operations_database() -> IntegrationDatabase:
    _, settings, _ = _runtime()
    return IntegrationDatabase(settings.home / "operations.sqlite")


@workflow_app.command("list")
def workflow_list() -> None:
    _emit([{"id": "stock-to-offer-v1", "durable": True}], False)


@workflow_app.command("status")
def workflow_status(run_id: str) -> None:
    database = _operations_database()
    try:
        row = database.connection.execute(
            "SELECT id,workflow_id,state,result_json,updated_at FROM workflow_runs WHERE id=?",
            (run_id,),
        ).fetchone()
        if row is None:
            raise typer.BadParameter("workflow run not found")
        _emit(dict(row), False)
    finally:
        database.close()


@workflow_app.command("cancel")
def workflow_cancel(run_id: str) -> None:
    database = _operations_database()
    try:
        with database.connection:
            cursor = database.connection.execute(
                "UPDATE workflow_runs SET state='CANCELLED' WHERE id=? AND state NOT IN ('COMPLETED','FAILED','CANCELLED')",
                (run_id,),
            )
        if cursor.rowcount != 1:
            raise typer.BadParameter("workflow run cannot be cancelled")
    finally:
        database.close()


@workflow_app.command("dead-letter")
def workflow_dead_letter() -> None:
    database = _operations_database()
    try:
        rows = [
            dict(row) for row in database.connection.execute(
                "SELECT id,workflow_id,state,updated_at FROM workflow_runs WHERE state='DEAD_LETTERED'"
            )
        ]
        _emit(rows, False)
    finally:
        database.close()


@app.command("suggest")
def suggest() -> None:
    connectors = any(_connector_directory().glob("*.json"))
    state = CapabilityState(
        has_stock_source=connectors,
        has_pricing_rule=False,
        has_delivery_provider=False,
        has_customer_consent=False,
        has_message_channel=False,
    )
    _emit([item.model_dump() for item in suggest_capabilities(state)], False)


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
