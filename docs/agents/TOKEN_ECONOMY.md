# Token Economy

## Purpose

Token controls limit context exposure and keep specialist use proportional to the task.

## Architecture

The six runtime definitions use registry budgets and maximum turns; the master applies lazy delegation across five specialists. Usage records are stored locally by run and session. The eight maintenance definitions are opt-in and accounted outside normal runs.

## Configuration

Adjust budgets only in the registry source, regenerate derived definitions, and evaluate the change. Model verbosity/reasoning profiles are configured separately. Maintenance definitions do not add runtime budget unless explicitly invoked.

## Commands

```powershell
skillshelf usage --last --json
skillshelf usage --session audit-1 --json
python scripts/generate-agents.py --check
```

## Examples

A direct deterministic route avoids a master-plus-specialist exchange. Memory uses progressive disclosure rather than loading all records.

## Failure Modes

Oversized briefs, broad delegation, repeated retries, or indiscriminate memory/tool output can exhaust limits. Usage may be absent when execution fails before recording.

## Security Boundaries

Context minimization is also a privacy boundary. Token budgets never authorize additional files, tools, memory, or external writes. Runtime-recorded usage is evidence; model estimates or explanations are interpretation.

## Tests

Token-efficiency evaluations compare lazy specialist use with broader delegation using offline fixture metrics. Credentialled token counts depend on the selected model/provider.

## Recovery

Narrow the task, inspect recent usage, resume with selected evidence, and avoid replaying full transcripts. Increase budgets only through reviewed registry changes.

## Known Limitations

Offline estimates are not billing guarantees. Provider token accounting and model behavior require credentials, while maintenance-agent cost is outside normal runtime totals.
