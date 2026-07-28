# Agent Runtime Overview

## Purpose

SkillShelf provides one master and five bounded specialists for normal user work, plus eight opt-in repository-maintenance definitions.

## Architecture

The six runtime definitions are `skillshelf-master`, `find-skills-agent`, `superpowers-agent`, `memory-agent`, `design-intelligence-agent`, and `skill-governor-agent`. They derive from `agents/registry.yml`. The eight maintenance definitions—behavioural eval, code review, Codex migration, design integration, MCP security, memory integration, release, and source audit—live under `agents/maintenance/definitions` and are not loaded by the runtime registry.

## Configuration

Configure model profiles in `agents/model-profiles.yml`, runtime policy in `agents/registry.yml`, and environment overrides through the profile variables. Maintenance agents require an explicit maintenance workflow; copying them into runtime directories is not configuration.

## Commands

```powershell
skillshelf agents --json
skillshelf doctor --json
python scripts/generate-agents.py --check
```

## Examples

`skillshelf ask "fix the failing parser test"` routes to the implementation specialist when the deterministic rule is confident. Ambiguous work stays with the master.

## Failure Modes

Registry drift, missing skill files, invalid policy, absent API credentials, or unavailable MCP services can prevent or limit execution. Maintenance definitions never compensate for a broken runtime automatically.

## Security Boundaries

Specialists receive bounded context, capabilities, MCP allowlists, token budgets, and prohibited actions. Model findings are interpretation; files changed, tests, artifacts, and tool executions are trustworthy only when attached from runtime-recorded evidence.

## Tests

Registry, routing, delegation, safety, token-efficiency, runtime-contract, governance, and behavioural evaluation checks cover the offline proof.

## Recovery

Run generation checks, restore registry/generated consistency, inspect `doctor`, and retry with the same session only after correcting configuration. Invoke maintenance definitions explicitly for repository repair.

## Known Limitations

Offline tests do not prove model quality, live MCP access, or credentialled OpenAI execution. The eight maintenance definitions are opt-in repository tools, not eight additional user-facing specialists.
