from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ReplayRequest:
    original_run_id: str
    canonical_input: dict[str, Any]
    configuration_version: str
    skill_hashes: dict[str, str]
    model_profile: str
    allow_live_connectors: bool = False
    allow_communications: bool = False

    def validate(self) -> None:
        if self.allow_communications:
            raise ValueError("replay never sends outbound communications automatically")
