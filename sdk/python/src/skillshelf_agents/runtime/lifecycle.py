from __future__ import annotations

from contextlib import AbstractAsyncContextManager
from typing import Any


class RuntimeLifecycle(AbstractAsyncContextManager["RuntimeLifecycle"]):
    """Owns async runtime services and closes them in reverse order."""

    def __init__(self, services: list[Any]) -> None:
        self.services = services
        self._entered: list[Any] = []

    async def __aenter__(self) -> "RuntimeLifecycle":
        for service in self.services:
            enter = getattr(service, "__aenter__", None)
            if enter is not None:
                await enter()
                self._entered.append(service)
        return self

    async def __aexit__(self, exc_type: Any, exc: Any, traceback: Any) -> bool:
        suppressed = False
        for service in reversed(self._entered):
            result = await service.__aexit__(exc_type, exc, traceback)
            suppressed = bool(result) or suppressed
        return suppressed
