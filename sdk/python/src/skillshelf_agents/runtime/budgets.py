from __future__ import annotations

from collections import defaultdict
import json
from typing import Any

from agents import ModelSettings, RunHooks
from pydantic import BaseModel, Field


class BudgetLimitExceeded(RuntimeError):
    pass


class UsageSummary(BaseModel):
    requests: int = 0
    input_tokens: int = 0
    cached_tokens: int = 0
    reasoning_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0

    def add(self, other: "UsageSummary") -> None:
        for name in type(self).model_fields:
            setattr(self, name, getattr(self, name) + getattr(other, name))


class RequestUsageSummary(UsageSummary):
    request_id: str
    agent_id: str


class ToolUsageSummary(BaseModel):
    calls: int = 0
    duration_seconds: float = 0
    failures: int = 0
    input_bytes: int = 0
    output_bytes: int = 0
    cost_units: float = 0


class BudgetScope(BaseModel):
    scope_id: str
    agent_id: str
    input_limit: int
    output_limit: int
    total_limit: int
    used_input: int = 0
    used_output: int = 0
    used_total: int = 0

    def can_accept_input(self, estimated_tokens: int) -> bool:
        return self.used_input + estimated_tokens <= self.input_limit

    def record(self, *, input_tokens: int, output_tokens: int) -> None:
        self.used_input += input_tokens
        self.used_output += output_tokens
        self.used_total += input_tokens + output_tokens


class TokenEstimate(BaseModel):
    tokens: int
    method: str


class BudgetExceededResult(BaseModel):
    status: str = "partially_completed"
    reason: str
    useful_evidence_preserved: bool
    evidence_ids: list[str] = Field(default_factory=list)


class BudgetLedger:
    def __init__(self, soft_limit: int, hard_limit: int) -> None:
        if soft_limit <= 0 or hard_limit < soft_limit:
            raise ValueError("invalid budget limits")
        self.soft_limit = soft_limit
        self.hard_limit = hard_limit
        self.run_total = UsageSummary()
        self.by_agent: dict[str, UsageSummary] = defaultdict(UsageSummary)
        self.by_tool: dict[str, ToolUsageSummary] = defaultdict(ToolUsageSummary)
        self.by_request: list[RequestUsageSummary] = []
        self.scopes: dict[str, BudgetScope] = {}
        self.input_estimates: list[dict[str, Any]] = []

    @property
    def optional_calls_allowed(self) -> bool:
        return self.run_total.total_tokens < self.soft_limit

    @property
    def hard_exhausted(self) -> bool:
        return self.run_total.total_tokens >= self.hard_limit

    def record_request(
        self,
        *,
        agent_id: str,
        request_id: str,
        input_tokens: int,
        output_tokens: int,
        cached_tokens: int = 0,
        reasoning_tokens: int = 0,
    ) -> RequestUsageSummary:
        item = RequestUsageSummary(
            request_id=request_id,
            agent_id=agent_id,
            requests=1,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cached_tokens=cached_tokens,
            reasoning_tokens=reasoning_tokens,
            total_tokens=input_tokens + output_tokens,
        )
        self.by_request.append(item)
        self.run_total.add(item)
        self.by_agent[agent_id].add(item)
        scope = self.scopes.get(agent_id)
        if scope is not None:
            scope.record(input_tokens=input_tokens, output_tokens=output_tokens)
        return item

    def register_scope(self, scope: BudgetScope) -> None:
        if scope.agent_id in self.scopes:
            raise ValueError(f"duplicate budget scope for agent {scope.agent_id!r}")
        self.scopes[scope.agent_id] = scope

    def enforce_input(self, agent_id: str, content: Any, *, model: str | None = None) -> TokenEstimate:
        estimate = estimate_tokens(content, model=model)
        self.input_estimates.append(
            {
                "agent_id": agent_id,
                "estimated_tokens": estimate.tokens,
                "method": estimate.method,
            }
        )
        scope = self.scopes.get(agent_id)
        if scope is not None and not scope.can_accept_input(estimate.tokens):
            raise BudgetLimitExceeded(
                f"input budget for {agent_id!r} would be exceeded "
                f"({scope.used_input}+{estimate.tokens}>{scope.input_limit})"
            )
        if self.run_total.total_tokens + estimate.tokens > self.hard_limit:
            raise BudgetLimitExceeded("run hard token budget would be exceeded by the next input")
        return estimate

    def record_tool(
        self,
        tool_name: str,
        duration_seconds: float,
        *,
        failed: bool,
        input_bytes: int = 0,
        output_bytes: int = 0,
        cost_units: float = 0,
    ) -> None:
        item = self.by_tool[tool_name]
        item.calls += 1
        item.duration_seconds += duration_seconds
        item.failures += int(failed)
        item.input_bytes += input_bytes
        item.output_bytes += output_bytes
        item.cost_units += cost_units


def estimate_tokens(content: Any, *, model: str | None = None) -> TokenEstimate:
    text = content if isinstance(content, str) else json.dumps(content, default=str)
    try:
        import tiktoken  # type: ignore[import-not-found]

        encoding = tiktoken.encoding_for_model(model) if model else tiktoken.get_encoding("cl100k_base")
        return TokenEstimate(tokens=len(encoding.encode(text)), method=f"tiktoken:{encoding.name}")
    except (ImportError, KeyError, ValueError):
        # Conservative UTF-8 fallback: one token per two bytes, rounded up.
        size = len(text.encode("utf-8"))
        return TokenEstimate(tokens=max(1, (size + 1) // 2), method="utf8-bytes/2-conservative")


def with_output_budget(settings: ModelSettings, output_token_budget: int) -> ModelSettings:
    if output_token_budget < 1:
        raise ValueError("output token budget must be positive")
    return settings.resolve(ModelSettings(max_tokens=output_token_budget))


class RuntimeBudgetHooks(RunHooks[Any]):
    def __init__(self, ledger: BudgetLedger) -> None:
        self.ledger = ledger

    async def on_llm_start(
        self,
        context: Any,
        agent: Any,
        system_prompt: str | None,
        input_items: list[Any],
    ) -> None:
        del context
        if self.ledger.hard_exhausted:
            raise BudgetLimitExceeded("hard token budget reached before the next model request")
        self.ledger.enforce_input(
            str(agent.name),
            {"system_prompt": system_prompt, "input_items": input_items},
            model=str(getattr(agent, "model", "")) or None,
        )

    async def on_llm_end(self, context: Any, agent: Any, response: Any) -> None:
        usage = response.usage
        if usage is None:
            return
        cached = getattr(usage.input_tokens_details, "cached_tokens", 0)
        reasoning = getattr(usage.output_tokens_details, "reasoning_tokens", 0)
        self.ledger.record_request(
            agent_id=agent.name,
            request_id=response.response_id or f"request-{len(self.ledger.by_request) + 1}",
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
            cached_tokens=cached,
            reasoning_tokens=reasoning,
        )
