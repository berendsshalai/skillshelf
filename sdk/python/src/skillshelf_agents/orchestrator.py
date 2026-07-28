from __future__ import annotations

import asyncio
import os
import uuid
from datetime import UTC, datetime
from typing import Any

from agents import Agent, Runner, SQLiteSession

from .agent_factory import AgentFactory
from .budgets import RuntimeBudgetHooks, UsageStore
from .config import Settings
from .contracts import Observation, OrchestratorResult, UsageSummary
from .event_log import EventLog
from .guardrails import validate_input, validate_output
from .mcp_runtime import MCPRuntime
from .registry import RuntimeRegistry
from .routing import route_task
from .sessions import SessionStore, scoped_session_id


class SkillShelfOrchestrator:
    def __init__(self, registry: RuntimeRegistry, factory: AgentFactory, settings: Settings) -> None:
        self.registry, self.factory, self.settings = registry, factory, settings
        settings.initialise()
        self.mcp = MCPRuntime(registry.root)
        self.usage_store = UsageStore(settings.home / "usage")
        self.events = EventLog(settings.home / "events")
        self.sessions = SessionStore(settings.home / "sessions" / "sessions.sqlite")
        self.budget_hooks = RuntimeBudgetHooks(settings.soft_token_limit, settings.hard_token_limit)
        self.specialists: dict[str, Agent] = {}
        self._master = self._build_master()

    def _build_master(self) -> Agent:
        tools: list[Any] = []
        for definition in self.registry.agents:
            self.mcp.assigned(definition.allowed_mcp)
            specialist = self.factory.build_specialist(definition)
            self.specialists[definition.id] = specialist
            tools.append(specialist.as_tool(
                definition.tool_name,
                definition.tool_description,
                max_turns=definition.max_turns,
                is_enabled=self.budget_hooks.optional_tool_enabled,
            ))
        model, model_settings = self.factory.model_for(self.registry.master.model_profile)
        instructions = (self.registry.root / self.registry.master.instruction_file).read_text(encoding="utf-8")
        return Agent(name=self.registry.master.display_name, instructions=instructions, model=model,
                     model_settings=model_settings, tools=tools, output_type=OrchestratorResult)

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

    async def run(self, task: str, *, session_id: str = "default", explicit_agent: str | None = None) -> OrchestratorResult:
        validate_input(task)
        if not os.getenv("OPENAI_API_KEY"):
            raise RuntimeError("OPENAI_API_KEY is required for model-backed ask/run commands")
        run_id = uuid.uuid4().hex
        scoped = scoped_session_id(self.registry.root, session_id)
        self.sessions.ensure(scoped)
        decision = route_task(task, explicit_agent)
        selected = explicit_agent or decision.direct_agent
        agent = self.specialists[selected] if selected else self._master
        sdk_session = SQLiteSession(scoped, str(self.settings.home / "sessions" / "agents-sdk.sqlite"))
        try:
            result = await asyncio.wait_for(
                Runner.run(agent, task, session=sdk_session,
                           hooks=self.budget_hooks,
                           max_turns=(self.registry.by_id(selected).max_turns if selected else self.registry.master.max_turns)),
                timeout=300,
            )
            output = result.final_output
            if selected:
                output = OrchestratorResult(status=output.status, answer=output.summary,
                                            specialists_used=[selected], evidence=output.evidence,
                                            files_changed=output.files_changed, tests_run=output.tests_run,
                                            unresolved_risks=output.risks)
            if not isinstance(output, OrchestratorResult):
                raise TypeError("runtime returned an invalid structured output")
            output.usage = self._usage(result)
            output.usage.budget_exceeded = output.usage.total_tokens >= self.settings.soft_token_limit
            validate_output(output.model_dump_json())
            self.usage_store.record(run_id, scoped, output.usage, output.specialists_used)
            self.events.append(Observation(
                run_id=run_id, timestamp=datetime.now(UTC).isoformat(),
                agents_used=output.specialists_used, skills_used=[
                    self.registry.by_id(item).skill for item in output.specialists_used
                ], routing_decision=decision.model_dump(), usage=output.usage.model_dump(),
                tool_failures=[], guardrail_events=[], user_corrections=[], evaluation_failures=[],
            ))
            return output
        except (asyncio.TimeoutError, KeyboardInterrupt) as exc:
            raise RuntimeError("agent run interrupted or timed out; completed evidence was preserved") from exc
        finally:
            await self.mcp.close()
