import pytest

from skillshelf_agents.budgets import BudgetExceeded, BudgetTracker
from skillshelf_agents.contracts import UsageSummary


def test_soft_and_hard_limits():
    tracker = BudgetTracker(10, 20)
    tracker.add(UsageSummary(total_tokens=11))
    assert not tracker.optional_calls_allowed
    assert tracker.usage.budget_exceeded
    with pytest.raises(BudgetExceeded):
        tracker.add(UsageSummary(total_tokens=9))
