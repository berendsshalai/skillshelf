from __future__ import annotations

import re
import hashlib
import json
from typing import Any

SECRET_KEYS = re.compile(r"(api.?key|token|password|cookie|authorization)", re.IGNORECASE)


def sanitise_event(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: ("[REDACTED]" if SECRET_KEYS.search(key) else sanitise_event(item))
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [sanitise_event(item) for item in value]
    if isinstance(value, tuple):
        return [sanitise_event(item) for item in value]
    return value


def event_digest(value: Any) -> str:
    payload = json.dumps(sanitise_event(value), sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
