from __future__ import annotations

import os
from typing import Protocol


class SecretStore(Protocol):
    def get(self, reference: str) -> str: ...


class EnvironmentSecretStore:
    """Resolve references from the process environment without retaining values."""

    def __init__(self, environment: dict[str, str] | None = None) -> None:
        self._environment = environment if environment is not None else os.environ

    def get(self, reference: str) -> str:
        if not reference or not reference.replace("_", "").isalnum():
            raise ValueError("invalid environment secret reference")
        value = self._environment.get(reference)
        if not value:
            raise KeyError(f"secret reference is not configured: {reference}")
        return value
