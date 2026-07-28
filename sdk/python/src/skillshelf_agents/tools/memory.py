from __future__ import annotations

from typing import Protocol


class MemoryReader(Protocol):
    async def search(self, query: str, limit: int) -> list[dict[str, object]]: ...

    async def timeline(self, observation_ids: list[str]) -> list[dict[str, object]]: ...

    async def get_observations(self, observation_ids: list[str]) -> list[dict[str, object]]: ...
