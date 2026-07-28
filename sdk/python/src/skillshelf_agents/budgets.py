from __future__ import annotations

import json
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from filelock import FileLock
from agents import RunHooks

from .contracts import UsageSummary


class BudgetExceeded(RuntimeError):
    pass


class BudgetTracker:
    def __init__(self, soft_limit: int, hard_limit: int) -> None:
        if soft_limit <= 0 or hard_limit < soft_limit:
            raise ValueError("invalid soft/hard token limits")
        self.soft_limit, self.hard_limit = soft_limit, hard_limit
        self.usage = UsageSummary()
        self.by_agent: dict[str, int] = defaultdict(int)
        self.by_tool: dict[str, int] = defaultdict(int)

    def add(self, usage: UsageSummary, *, agent: str | None = None, tool: str | None = None) -> None:
        for field in (
            "requests",
            "input_tokens",
            "output_tokens",
            "cached_tokens",
            "reasoning_tokens",
            "total_tokens",
        ):
            setattr(self.usage, field, getattr(self.usage, field) + getattr(usage, field))
        if agent:
            self.by_agent[agent] += usage.total_tokens
        if tool:
            self.by_tool[tool] += usage.total_tokens
        self.usage.budget_exceeded = self.usage.total_tokens >= self.soft_limit
        if self.usage.total_tokens >= self.hard_limit:
            raise BudgetExceeded("hard token limit reached; further delegation stopped")

    @property
    def optional_calls_allowed(self) -> bool:
        return self.usage.total_tokens < self.soft_limit


class RuntimeBudgetHooks(RunHooks[Any]):
    def __init__(self, soft_limit: int, hard_limit: int) -> None:
        self.soft_limit, self.hard_limit = soft_limit, hard_limit

    async def on_llm_start(
        self, context: Any, agent: Any, system_prompt: str | None, input_items: list[Any]
    ) -> None:
        if context.usage.total_tokens >= self.hard_limit:
            raise BudgetExceeded("hard token limit reached; further model delegation stopped")

    def optional_tool_enabled(self, context: Any, _agent: Any) -> bool:
        return bool(context.usage.total_tokens < self.soft_limit)


class UsageStore:
    def __init__(self, directory: Path) -> None:
        self.directory = directory
        self.directory.mkdir(parents=True, exist_ok=True)

    def record(self, run_id: str, session_id: str, usage: UsageSummary, agents: list[str]) -> Path:
        path = self.directory / f"{run_id}.json"
        payload = {
            "run_id": run_id,
            "session_id": session_id,
            "timestamp": datetime.now(UTC).isoformat(),
            "usage": usage.model_dump(),
            "agents": agents,
        }
        with FileLock(str(path) + ".lock"):
            path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        return path

    def query(self, *, session: str | None = None, agent: str | None = None) -> list[dict[str, Any]]:
        records = [json.loads(path.read_text(encoding="utf-8")) for path in self.directory.glob("*.json")]
        if session:
            records = [item for item in records if item["session_id"] == session]
        if agent:
            records = [item for item in records if agent in item["agents"]]
        return sorted(records, key=lambda item: item["timestamp"])
