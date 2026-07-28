from __future__ import annotations

import hashlib
import json
import uuid
from contextlib import contextmanager
from typing import Any, Iterator

from .models import ToolCallStatus
from .repository import RunLedger


class ToolCallRecorder:
    def __init__(self, ledger: RunLedger, run_id: str, agent_id: str) -> None:
        self.ledger = ledger
        self.run_id = run_id
        self.agent_id = agent_id

    @contextmanager
    def record(self, tool_name: str, arguments: dict[str, Any]) -> Iterator[str]:
        tool_call_id = f"call-{uuid.uuid4().hex}"
        digest = hashlib.sha256(
            json.dumps(arguments, sort_keys=True, separators=(",", ":"), default=str).encode()
        ).hexdigest()
        self.ledger.start_tool_call(
            run_id=self.run_id,
            tool_call_id=tool_call_id,
            agent_id=self.agent_id,
            tool_name=tool_name,
            arguments_digest=digest,
        )
        try:
            yield tool_call_id
        except Exception as exc:
            self.ledger.finish_tool_call(
                tool_call_id,
                status=ToolCallStatus.FAILED,
                error_code=type(exc).__name__,
            )
            raise
        else:
            self.ledger.finish_tool_call(
                tool_call_id,
                status=ToolCallStatus.COMPLETED,
            )
