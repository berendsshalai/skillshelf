from __future__ import annotations

import re
from typing import Any

SECRET_KEYS = re.compile(r"(api.?key|token|password|cookie|authorization)", re.IGNORECASE)


def sanitise_event(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: ("[REDACTED]" if SECRET_KEYS.search(key) else sanitise_event(item))
                for key, item in value.items()}
    if isinstance(value, list):
        return [sanitise_event(item) for item in value]
    return value
