# SkillShelf Master

## Purpose

The master owns user communication, task decomposition, routing, budget control, evidence reconciliation, and final truthfulness.

## Architecture

`skillshelf-master` is one of six runtime definitions and can call the five specialists as tools. The eight maintenance definitions are opt-in and outside its normal tool set. Delegation depth is capped at two; independent read-only work may run in parallel.

## Configuration

The master definition, instruction file, model profile, maximum turns, and output contract come from `agents/registry.yml`. `SKILLSHELF_MODEL_ORCHESTRATOR` can override its configured model.

## Commands

```powershell
skillshelf ask "audit this change" --session audit-1 --json
skillshelf usage --last --json
```

## Examples

A request spanning design and implementation stays with the master, which may sequence design intelligence before superpowers and reconcile both reports.

## Failure Modes

Ambiguous delegation, budget exhaustion, invalid structured output, model/API errors, and unavailable specialist tools produce errors or partial results. The master must not invent missing execution evidence.

## Security Boundaries

The master selects the smallest sufficient specialist set, does not disclose all memory or skills, and retains approval decisions. Model summaries and findings remain interpretation; runtime evidence overwrites model-authored execution claims.

## Tests

Routing, delegation, safety, structured-contract, and token-efficiency evaluations exercise master behavior offline. Credentialled model behavior requires separate opt-in evaluation.

## Recovery

Retry a transient credentialled failure using the same session, or explicitly select a specialist when routing is the only problem. At a hard budget limit, preserve truthful partial results.

## Known Limitations

Deterministic rules are narrow, model orchestration requires credentials, and no offline test guarantees judgment quality. Maintenance agents are not callable by the master’s normal registry.
