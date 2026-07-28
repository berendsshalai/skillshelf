from __future__ import annotations

from typing import Protocol


class GovernanceWriter(Protocol):
    def write_observation(self, payload: dict[str, object]) -> str: ...

    def create_staged_update(self, payload: dict[str, object]) -> str: ...
