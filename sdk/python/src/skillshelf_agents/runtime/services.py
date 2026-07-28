from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .approvals import ApprovalStore
from .budgets import BudgetLedger


@dataclass(frozen=True)
class RuntimeServices:
    approvals: ApprovalStore
    budgets: BudgetLedger
    ledger: Any
