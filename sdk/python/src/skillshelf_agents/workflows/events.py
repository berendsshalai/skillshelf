from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel


class WorkflowEvent(BaseModel):
    id: int
    run_id: str
    event_type: str
    payload: dict[str, Any]
    created_at: datetime
