from __future__ import annotations

import asyncio
import os
import uuid
from datetime import UTC, datetime
from typing import Any

from agents import Agent, RunHooks, Runner

from .agent_factory import AgentFactory
from .budgets import UsageStore
from .contracts import Observation, OrchestratorResult, SpecialistResult, UsageSummary
from .event_log import EventLog
from .guardrails import validate_input, validate_output
from .ledger import RunLedger
from .ledger.models import RunStatus
from .registry import RuntimeRegistry
from .routing import route_task
from .runtime import DelegationInput, RuntimeContext, build_delegation_prompt
from .runtime.budgets import BudgetLedger, RuntimeBudgetHooks
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

    def _build_agents(self, budget_ledger: BudgetLedger) -> OperationalRunHooks:
        budget_hooks = RuntimeBudgetHooks(budget_ledger)
        specialist_tool_names = {item.tool_name: item.id for item in self.registry.agents}
        hooks = OperationalRunHooks(budget_hooks, specialist_tool_names)
        tools: list[Any] = []
        self.specialists = {}
        for definition in self.registry.agents:
            local_capabilities = [
                item for item in definition.allowed_capabilities if self.tool_registry.supports(item)
            ]
            function_tools = self.tool_registry.build(local_capabilities)
            specialist = self.factory.build_specialist(definition, tools=function_tools)
            self.specialists[definition.id] = specialist

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
            configuration_version="0.3.0",
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
        hooks = self._build_agents(budget_ledger)
        agent = self.specialists[selected] if selected else self._master
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
                output = OrchestratorResult(
                    status=output.status,
                    answer=output.summary,
                    specialists_used=[selected],
                    evidence=output.evidence,
                    files_changed=output.files_changed,
                    tests_run=output.tests_run,
                    unresolved_risks=output.risks,
                )
            if not isinstance(output, OrchestratorResult):
                raise TypeError("runtime returned an invalid structured output")
            output.specialists_used = [selected] if selected else hooks.specialists_used
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
