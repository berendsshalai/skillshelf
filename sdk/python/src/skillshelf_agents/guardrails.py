from __future__ import annotations

import re
from pathlib import Path

BLOCKED_INPUT = (
    r"(print|show|expose).{0,20}(api key|password|token|secret)",
    r"(bypass|ignore).{0,20}(mcp|permission|skill)",
    r"(force push|reset --hard|silently star|automatically star)",
)
SECRET_PATTERN = re.compile(r"(sk-[A-Za-z0-9_-]{16,}|gh[pousr]_[A-Za-z0-9]{20,})")


class GuardrailViolation(ValueError):
    pass


def validate_input(task: str) -> None:
    if any(re.search(pattern, task, re.IGNORECASE) for pattern in BLOCKED_INPUT):
        raise GuardrailViolation("request violates SkillShelf input policy")


def validate_write(path: Path, root: Path, *, approved: bool, destructive: bool = False) -> Path:
    resolved, boundary = path.resolve(), root.resolve()
    if boundary not in resolved.parents and resolved != boundary:
        raise GuardrailViolation("write path is outside the permitted root")
    if "upstream" in resolved.parts:
        raise GuardrailViolation("upstream submodules are immutable")
    if (destructive or ".git" in resolved.parts) and not approved:
        raise GuardrailViolation("sensitive write requires explicit approval")
    return resolved


def validate_output(text: str) -> None:
    if SECRET_PATTERN.search(text):
        raise GuardrailViolation("output contains a credential-like value")
