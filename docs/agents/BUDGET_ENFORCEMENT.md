# Budget Enforcement

## Purpose

SkillShelf bounds model input, model output and tool activity per run and per specialist.

## Architecture

The budget ledger reserves estimated input before each request, applies SDK output-token settings,
records actual usage afterward and counts tool calls, duration and output bytes. Soft limits stop
optional work; hard limits prevent the next request and produce a persisted partial result.

## Configuration

Global defaults come from runtime settings and agent-specific input/output limits come from
`agents/registry.yml`. Tool ceilings are declared with the capability policy.

## Commands

Use `skillshelf usage --last --json`, `skillshelf runs inspect RUN_ID --json`, and
`skillshelf doctor --deep --json`.

## Example

When a 120-token hard limit is reached, the next model request is blocked while already recorded
tool evidence remains attached to the partial result.

## Security boundaries

Agents cannot raise their own ceilings. Cached and reasoning token fields remain separately
observable, and tool output is truncated before it can inflate later model input.

## Failure modes

Unestimable input fails conservatively. Missing usage metadata is recorded as an accounting error.
Hard exhaustion is terminal or partial according to the run contract, never silently ignored.

## Tests

Budget tests cover input preflight, output settings, per-agent ceilings, tool counts/bytes/time,
soft degradation, hard exhaustion and evidence-preserving partial results.

## Recovery

Start a new explicitly budgeted run or reduce the task scope. A completed or exhausted run's
accounting records are immutable.

## Known limitations

Pre-request input measurement is a conservative deterministic estimate; provider-reported actual
tokens remain authoritative after a response.
