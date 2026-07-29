from __future__ import annotations

from datetime import datetime, timedelta

from .definitions import RetryPolicy


def next_retry_at(policy: RetryPolicy, attempt: int, now: datetime) -> datetime:
    return now + timedelta(seconds=policy.delay(attempt))


def is_retryable(policy: RetryPolicy, error: BaseException) -> bool:
    return type(error).__name__ in policy.retryable_errors
