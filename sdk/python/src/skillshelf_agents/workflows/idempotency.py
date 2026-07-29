from __future__ import annotations

import hashlib
import json
from typing import Any


def idempotency_key(workflow_id: str, value: dict[str, Any]) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(f"{workflow_id}|{payload}".encode()).hexdigest()
