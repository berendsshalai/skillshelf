# Evaluations

## Purpose

Evaluations detect routing, delegation, safety, behavior, and token-efficiency regressions before runtime or maintenance changes are accepted.

## Architecture

YAML suites cover routing, delegation, safety, and token efficiency; generated reports capture results. Normal execution has six runtime definitions. Behavioural evaluation is one of eight opt-in maintenance definitions, not a seventh runtime agent.

## Configuration

Use deterministic fixtures for offline checks. Enable credentialled suites only when provider keys and explicit cost authority are present, and label their results separately.

## Commands

```powershell
& sdk/python/.venv/Scripts/python.exe -m pytest -q --basetemp work/pytest-agents
python scripts/generate-agents.py --check
```

## Examples

An offline routing case asserts a specialist ID and confidence. A live judge may interpret response quality, but cannot replace runtime evidence for files, tests, or tool calls.

## Failure Modes

Stale fixtures, nondeterministic judges, missing credentials, provider limits, and generated-report drift can produce failures or skipped checks.

## Security Boundaries

Do not send sensitive fixtures to live models. Runtime-derived hashes and execution records are facts; evaluator/model ratings are interpretations.

## Tests

Report offline pass/fail/skip counts separately from credentialled model runs. Never describe skipped live evaluations as passed.

## Recovery

Reproduce deterministic failures locally, inspect fixture and runtime changes, then rerun. Retry live evaluations only after addressing credentials or rate limits.

## Known Limitations

Offline suites cannot measure full model quality. Credentialled results vary by model and time, and maintenance evaluation definitions require explicit invocation.
