from __future__ import annotations

import asyncio
import os
import uuid
from datetime import UTC, datetime
from typing import Any

from agents import Agent, RunHooks, Runner

from .agent_factory import AgentFactory
from .budgets import UsageStore
from .contracts import (
    FileChange,
    Observation,
    OrchestratorResult,
    SpecialistResult,
    TestExecution,
    UsageSummary,
)
from .event_log import EventLog
from .guardrails import validate_input, validate_output
from .ledger import RunLedger
from .ledger.models import RunStatus
from .registry import RuntimeRegistry
from .mcp import MCPAssignment, MCPAssignmentResolver, StaticHostToolProvider
from .mcp_runtime import MCPRuntime
from .routing import route_task
from .runtime import (
    CapabilityProviderType,
    CapabilityResolver,
    DelegationInput,
    RunEvidenceRecorder,
    RuntimeContext,
    build_delegation_prompt,
)
from .runtime.budgets import (
    BudgetLedger,
    BudgetLimitExceeded,
    BudgetScope,
    RuntimeBudgetHooks,
)
from .runtime.evidence import validate_evidence_references
from .sessions import SessionStore, UnifiedSessionManager
from .sessions.identity import repository_identity
from .tools import CapabilityToolRegistry
from .tools.artefacts import ArtifactStore
from .tools.filesystem import RepositoryFilesystem
from .tools.subprocess import SafeCommandExecutor
from .config import Settings


class OperationalRunHooks(RunHooks[Any]):
    def __init__(
        self,
        budgets: RuntimeBudgetHooks,
        specialist_tools: dict[str, str],
    ) -> None:
        self.budgets = budgets
        self.specialist_tools = specialist_tools
        self.specialists_used: list[str] = []
        self.tools_used: list[str] = []

    async def on_llm_start(
        self,
        context: Any,
        agent: Any,
        system_prompt: str | None,
        input_items: list[Any],
    ) -> None:
        await self.budgets.on_llm_start(context, agent, system_prompt, input_items)

    async def on_llm_end(self, context: Any, agent: Any, response: Any) -> None:
        await self.budgets.on_llm_end(context, agent, response)

    async def on_tool_start(self, context: Any, agent: Any, tool: Any) -> None:
        del context, agent
        name = str(tool.name)
        self.tools_used.append(name)
        specialist = self.specialist_tools.get(name)
        if specialist and specialist not in self.specialists_used:
            self.specialists_used.append(specialist)


class SkillShelfOrchestrator:
    def __init__(self, registry: RuntimeRegistry, factory: AgentFactory, settings: Settings) -> None:
        self.registry, self.factory, self.settings = registry, factory, settings
        settings.initialise()
        self.usage_store = UsageStore(settings.home / "usage")
        self.events = EventLog(settings.home / "events")
        session_database = settings.home / "sessions" / "skillshelf.sqlite"
        self.session_manager = UnifiedSessionManager(session_database)
        self.sessions = SessionStore(session_database)
        self.ledger = RunLedger(settings.home / "runs" / "ledger.sqlite")
        artifacts = ArtifactStore(settings.home / "artifacts")
        filesystem = RepositoryFilesystem(
            registry.root,
            settings.home / "backups" / "filesystem",
        )
        commands = SafeCommandExecutor(registry.root, artifacts)
        self.tool_registry = CapabilityToolRegistry(filesystem=filesystem, commands=commands)
        self.specialists: dict[str, Agent] = {}
        self._master: Agent
        self._build_agents(BudgetLedger(settings.soft_token_limit, settings.hard_token_limit))

    @staticmethod
    async def _compact_specialist_output(result: Any) -> str:
        output = result.final_output
        if isinstance(output, SpecialistResult):
            return output.model_dump_json(
                include={
                    "agent_id",
                    "status",
                    "summary",
                    "findings",
                    "evidence",
                    "risks",
                    "next_action",
                    "context_for_master",
                }
            )
        return str(output)

    def _build_agents(
        self,
        budget_ledger: BudgetLedger,
        *,
        assignments: dict[str, MCPAssignment] | None = None,
        strict: bool = False,
    ) -> OperationalRunHooks:
        budget_hooks = RuntimeBudgetHooks(budget_ledger)
        specialist_tool_names = {item.tool_name: item.id for item in self.registry.agents}
        hooks = OperationalRunHooks(budget_hooks, specialist_tool_names)
        tools: list[Any] = []
        self.specialists = {}
        for definition in self.registry.agents:
            assignment = (assignments or {}).get(definition.id)
            if strict and assignment is not None:
                report = CapabilityResolver(self.tool_registry).resolve(definition, mcp_assignment=assignment)
                local_capabilities = [
                    item.capability
                    for item in report.resolutions
                    if item.provider_type == CapabilityProviderType.FUNCTION_TOOL
                ]
            else:
                # Construction used only for metadata/lazy-skill introspection. Actual
                # execution always takes the strict run-scoped path below.
                local_capabilities = [
                    item for item in definition.allowed_capabilities if self.tool_registry.supports(item)
                ]
            function_tools = self.tool_registry.build(local_capabilities)
            if assignment is not None:
                by_name = {tool.name: tool for tool in [*function_tools, *assignment.host_tools]}
                function_tools = list(by_name.values())
            specialist = self.factory.build_specialist(
                definition,
                tools=function_tools,
                mcp_servers=assignment.connected_servers if assignment is not None else [],
            )
            self.specialists[definition.id] = specialist
            budget_ledger.register_scope(
                BudgetScope(
                    scope_id=f"agent:{definition.id}",
                    agent_id=definition.display_name,
                    input_limit=definition.token_budget.input,
                    output_limit=definition.token_budget.output,
                    total_limit=definition.token_budget.input + definition.token_budget.output,
                )
            )

            async def needs_approval(
                context: Any,
                parameters: dict[str, Any],
                _call_id: str,
                *,
                allowed: frozenset[str] = frozenset(definition.allowed_capabilities),
            ) -> bool:
                delegation = DelegationInput.model_validate(parameters)
                if not set(delegation.allowed_capabilities).issubset(allowed):
                    raise PermissionError("delegation requests an undeclared capability")
                runtime = context.context
                if (
                    isinstance(runtime, RuntimeContext)
                    and runtime.delegation_depth >= runtime.max_delegation_depth
                ):
                    raise PermissionError("maximum delegation depth reached")
                return False

            def optional_specialist_enabled(
                _context: Any,
                _agent: Any,
                *,
                ledger: BudgetLedger = budget_ledger,
            ) -> bool:
                return ledger.optional_calls_allowed

            tools.append(
                specialist.as_tool(
                    definition.tool_name,
                    definition.tool_description,
                    parameters=DelegationInput,
                    input_builder=build_delegation_prompt,
                    include_input_schema=True,
                    custom_output_extractor=self._compact_specialist_output,
                    needs_approval=needs_approval,
                    max_turns=definition.max_turns,
                    hooks=budget_hooks,
                    is_enabled=optional_specialist_enabled,
                )
            )
        model, model_settings = self.factory.model_for(self.registry.master.model_profile)
        base = (self.registry.root / self.registry.master.instruction_file).read_text(encoding="utf-8")

        async def master_instructions(context: Any, _agent: Agent) -> str:
            runtime = context.context
            envelope = ""
            if isinstance(runtime, RuntimeContext):
                envelope = (
                    f"\n\nCurrent run_id: {runtime.run_id}\nCurrent trace_id: {runtime.trace_id}\n"
                    "Populate every DelegationInput with these exact identifiers and the selected "
                    "specialist's declared capability and token limits."
                )
            return base + envelope

        self._master = Agent(
            name=self.registry.master.display_name,
            instructions=master_instructions,
            model=model,
            model_settings=model_settings,
            tools=tools,
            output_type=OrchestratorResult,
        )
        return hooks

    def _host_providers(self) -> list[StaticHostToolProvider]:
        providers: list[StaticHostToolProvider] = []
        for item in MCPRuntime(self.registry.root).servers.values():
            if item.adapter != "host-provided":
                continue
            if (
                "optional" in item.installation_status.casefold()
                or "external" in item.installation_status.casefold()
            ):
                continue

            def build_tools(
                definition: Any,
                _context: RuntimeContext,
                *,
                registry: CapabilityToolRegistry = self.tool_registry,
            ) -> list[Any]:
                supported = [
                    capability
                    for capability in definition.allowed_capabilities
                    if registry.supports(capability)
                ]
                return registry.build(supported)

            providers.append(StaticHostToolProvider(item.name, build_tools))
        return providers

    async def _resolve_assignments(
        self,
        runtime_context: RuntimeContext,
        selected: str | None,
        mcp_runtime: MCPRuntime,
    ) -> dict[str, MCPAssignment]:
        resolver = MCPAssignmentResolver(mcp_runtime, self._host_providers())
        definitions = [self.registry.by_id(selected)] if selected is not None else self.registry.agents
        assignments: dict[str, MCPAssignment] = {}
        for definition in definitions:
            assignments[definition.id] = await resolver.resolve_for_agent(definition, runtime_context)
        return assignments

    @staticmethod
    def _usage(result: Any) -> UsageSummary:
        usage = result.context_wrapper.usage
        return UsageSummary(
            requests=usage.requests,
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
            cached_tokens=usage.input_tokens_details.cached_tokens,
            reasoning_tokens=usage.output_tokens_details.reasoning_tokens,
            total_tokens=usage.total_tokens,
        )

    async def run(
        self,
        task: str,
        *,
        session_id: str = "default",
        explicit_agent: str | None = None,
    ) -> OrchestratorResult:
        validate_input(task)
        run_id = uuid.uuid4().hex
        trace_id = uuid.uuid4().hex
        identity = repository_identity(self.registry.root)
        scoped = f"{identity}:{session_id}"
        self.sessions.ensure(scoped)
        self.ledger.create_run(
            run_id=run_id,
            trace_id=trace_id,
            session_id=scoped,
            canonical_input={"task": task, "explicit_agent": explicit_agent},
            configuration_version="0.4.0",
        )
        decision = route_task(task, explicit_agent)
        self.ledger.transition(run_id, RunStatus.ROUTED)
        if not os.getenv("OPENAI_API_KEY"):
            self.ledger.record_error(
                run_id,
                code="missing_model_credentials",
                message="OPENAI_API_KEY is required for model-backed ask/run commands",
            )
            self.ledger.transition(run_id, RunStatus.FAILED)
            raise RuntimeError("OPENAI_API_KEY is required for model-backed ask/run commands")

        selected = explicit_agent or decision.direct_agent
        budget_ledger = BudgetLedger(self.settings.soft_token_limit, self.settings.hard_token_limit)
        runtime_context = RuntimeContext(
            run_id=run_id,
            trace_id=trace_id,
            session_id=scoped,
            repository_root=self.registry.root,
            repository_identity=identity,
            approval_grants=set(),
            soft_token_limit=self.settings.soft_token_limit,
            hard_token_limit=self.settings.hard_token_limit,
            max_delegation_depth=self.settings.max_delegation_depth,
        )
        evidence = RunEvidenceRecorder(run_id, ledger=self.ledger)
        self.tool_registry.bind_evidence(evidence, agent_id=selected or self.registry.master.id)
        mcp_runtime = MCPRuntime(self.registry.root)
        try:
            assignments = await self._resolve_assignments(runtime_context, selected, mcp_runtime)
            for agent_id, assignment in assignments.items():
                for server, digest in assignment.tool_list_digests.items():
                    evidence.record_mcp_connection(
                        server_name=server,
                        agent_id=agent_id,
                        status="connected",
                        tool_list_digest=digest,
                        tool_names=assignment.provider_tools.get(server, []),
                    )
                for degraded in assignment.degraded:
                    evidence.record_mcp_connection(
                        agent_id=agent_id,
                        status="degraded",
                        **degraded.model_dump(),
                    )
            hooks = self._build_agents(budget_ledger, assignments=assignments, strict=True)
            agent = self.specialists[selected] if selected else self._master
        except BaseException as exc:
            self.ledger.record_error(run_id, code=type(exc).__name__, message=str(exc))
            self.ledger.transition(run_id, RunStatus.FAILED)
            try:
                await mcp_runtime.close()
            except BaseException:
                pass
            raise
        run_input: str = task
        if selected:
            definition = self.registry.by_id(selected)
            run_input = build_delegation_prompt(
                {
                    "params": DelegationInput(
                        task=task,
                        success_criteria=["Return a verified result for the requested task."],
                        allowed_capabilities=definition.allowed_capabilities,
                        prohibited_capabilities=definition.prohibited_capabilities,
                        input_token_budget=definition.token_budget.input,
                        output_token_budget=definition.token_budget.output,
                        run_id=run_id,
                        trace_id=trace_id,
                    )
                }
            )
        self.ledger.transition(run_id, RunStatus.RUNNING)
        try:
            result = await asyncio.wait_for(
                Runner.run(
                    agent,
                    run_input,
                    context=runtime_context,
                    session=self.session_manager.sdk_session(scoped),
                    hooks=hooks,
                    max_turns=(
                        self.registry.by_id(selected).max_turns
                        if selected
                        else self.registry.master.max_turns
                    ),
                ),
                timeout=300,
            )
            output = result.final_output
            if selected:
                mechanical = evidence.evidence_for_agent_invocation(selected)
                output = OrchestratorResult(
                    status=output.status,
                    answer=output.summary,
                    specialists_used=[selected],
                    evidence=validate_evidence_references(output.evidence, evidence.evidence_for_run()),
                    files_changed=mechanical.files_changed,
                    tests_run=[
                        TestExecution(
                            command=" ".join(item.command),
                            status="passed" if item.exit_code == 0 else "failed",
                            exit_code=item.exit_code,
                            artifact_id=item.stdout_artifact_id,
                        )
                        for item in mechanical.tests_run
                    ],
                    unresolved_risks=output.risks,
                )
            if not isinstance(output, OrchestratorResult):
                raise TypeError("runtime returned an invalid structured output")
            output.specialists_used = [selected] if selected else hooks.specialists_used
            if not selected:
                run_evidence = evidence.evidence_for_run()
                output.evidence = validate_evidence_references(output.evidence, run_evidence)
                output.files_changed = [
                    FileChange(
                        path=item["path"],
                        action=item["action"],
                        summary=(
                            f"{item['before_sha256'] or 'absent'} -> {item['after_sha256'] or 'absent'}"
                        ),
                    )
                    for item in run_evidence["file_changes"]
                ]
                output.tests_run = [
                    TestExecution(
                        command=" ".join(item["command"]),
                        status="passed" if item["exit_code"] == 0 else "failed",
                        exit_code=item["exit_code"],
                        artifact_id=item["stdout_artifact_id"],
                    )
                    for item in run_evidence["tests"]
                ]
            output.usage = self._usage(result)
            output.usage.budget_exceeded = not budget_ledger.optional_calls_allowed
            for request in budget_ledger.by_request:
                self.ledger.record_usage(
                    run_id=run_id,
                    agent_id=request.agent_id,
                    request_id=request.request_id,
                    input_tokens=request.input_tokens,
                    cached_tokens=request.cached_tokens,
                    reasoning_tokens=request.reasoning_tokens,
                    output_tokens=request.output_tokens,
                )
            validate_output(output.model_dump_json())
            self.usage_store.record(run_id, scoped, output.usage, output.specialists_used)
            self.events.append(
                Observation(
                    run_id=run_id,
                    timestamp=datetime.now(UTC).isoformat(),
                    agents_used=output.specialists_used,
                    skills_used=[self.registry.by_id(item).skill for item in output.specialists_used],
                    routing_decision=decision.model_dump(),
                    usage=output.usage.model_dump(),
                    tool_failures=[],
                    guardrail_events=[],
                    user_corrections=[],
                    evaluation_failures=[],
                )
            )
            self.events.record_event(
                run_id=run_id,
                trace_id=trace_id,
                session_id=scoped,
                agent_ids=output.specialists_used,
                skill_hashes={
                    item: self.factory.skill_loader.load_skill(self.registry.by_id(item).skill).sha256
                    for item in output.specialists_used
                },
                event_type="run_completed",
                severity="info",
                details={
                    "status": output.status,
                    "tool_failures": [
                        item
                        for items in evidence.evidence_for_run()["agents"].values()
                        for item in items
                        if item["status"] != "completed"
                    ],
                },
            )
            terminal = (
                RunStatus.PARTIALLY_COMPLETED
                if output.status == "partially_completed"
                else RunStatus.COMPLETED
            )
            self.ledger.transition(run_id, terminal)
            return output
        except asyncio.TimeoutError as exc:
            self.ledger.record_error(run_id, code="timeout", message=str(exc))
            self.ledger.transition(run_id, RunStatus.TIMED_OUT)
            raise RuntimeError("agent run timed out; inspect the run ledger for persisted evidence") from exc
        except BudgetLimitExceeded as exc:
            useful = bool(
                evidence.evidence_for_run()["file_changes"]
                or evidence.evidence_for_run()["artifacts"]
                or evidence.evidence_for_run()["tests"]
            )
            output = OrchestratorResult(
                status="partially_completed" if useful else "blocked",
                answer=(
                    "Execution stopped because the hard token budget was reached."
                    if useful
                    else "The hard token budget was reached before useful evidence was produced."
                ),
                specialists_used=[selected] if selected else hooks.specialists_used,
                files_changed=[
                    FileChange(
                        path=item["path"],
                        action=item["action"],
                        summary="mechanically recorded before budget exhaustion",
                    )
                    for item in evidence.evidence_for_run()["file_changes"]
                ],
            )
            output.usage = UsageSummary(
                requests=budget_ledger.run_total.requests,
                input_tokens=budget_ledger.run_total.input_tokens,
                output_tokens=budget_ledger.run_total.output_tokens,
                cached_tokens=budget_ledger.run_total.cached_tokens,
                reasoning_tokens=budget_ledger.run_total.reasoning_tokens,
                total_tokens=budget_ledger.run_total.total_tokens,
                budget_exceeded=True,
            )
            self.ledger.record_error(run_id, code="budget_exhausted", message=str(exc))
            self.ledger.transition(run_id, RunStatus.PARTIALLY_COMPLETED)
            return output
        except BaseException as exc:
            if isinstance(exc, KeyboardInterrupt):
                terminal = RunStatus.CANCELLED
            else:
                terminal = RunStatus.FAILED
            self.ledger.record_error(run_id, code=type(exc).__name__, message=str(exc))
            try:
                self.ledger.transition(run_id, terminal)
            except ValueError:
                pass
            raise
        finally:
            try:
                await mcp_runtime.close()
            except BaseException as cleanup_error:
                self.events.record_event(
                    run_id=run_id,
                    trace_id=trace_id,
                    session_id=scoped,
                    event_type="mcp_cleanup_failed",
                    severity="error",
                    details={"error": type(cleanup_error).__name__},
                )
