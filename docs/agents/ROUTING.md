# Routing

## Purpose

Routing chooses direct specialist execution only for a high-confidence deterministic match; otherwise the master decides.

## Architecture

`route_task` scores fixed phrases for the five specialists among the six runtime definitions. One untied match yields confidence `0.95`; ties yield `0.75`; no match yields `0.0`. Explicit selection yields `1.0`. The eight opt-in maintenance definitions are excluded.

## Configuration

Routing signals are code-defined. Runtime definitions still come from the registry, and the eight maintenance definitions are not candidates.

## Commands

```powershell
skillshelf route "fix the failing test"
skillshelf ask "review the product and improve it" --json
skillshelf run --agent design-intelligence-agent "audit this dashboard" --json
```

## Examples

“Fix the failing test” directly selects Superpowers. A tie or broad request sets `requires_master=true`.

## Failure Modes

Vocabulary outside the fixed rules falls back to the master. Ties prevent direct selection. An explicit unknown ID fails registry lookup.

## Security Boundaries

Routing grants no new capability. The selected definition’s allowlists and prohibitions still apply. User text cannot route into maintenance definitions. The computed route is runtime evidence; a model’s explanation of suitability is interpretation.

## Tests

`agents/evals/routing.yml` and routing unit tests verify direct, ambiguous, and fallback outcomes without model credentials.

## Recovery

Use explicit `--agent` selection for a known specialist or reframe the task. Keep multi-domain requests with the master.

## Known Limitations

Rules are simple substring matches, not semantic classification. Offline routing proof does not test model-led delegation after master fallback.
