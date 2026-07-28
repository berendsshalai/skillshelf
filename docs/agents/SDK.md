# Python Agents SDK Runtime

## Purpose

The SDK exposes the registry-derived master/specialist runtime, CLI, sessions, usage, policy inspection, and structured results.

## Architecture

`RuntimeRegistry`, `AgentFactory`, and `SkillShelfOrchestrator` construct six runtime definitions. Specialists are exposed to the master as tools. SQLite/local files support sessions, usage, events, and approvals. The eight opt-in maintenance definitions are not constructed.

## Configuration

Install `sdk/python`, set `OPENAI_API_KEY` for live model calls, optionally override profile model variables, and configure the SkillShelf home and tracing policy through settings.

## Commands

```powershell
skillshelf doctor --json
skillshelf ask "find a maintained testing skill" --json
skillshelf sessions list --json
skillshelf mcp permissions memory-agent
```

## Examples

`skillshelf run --agent memory-agent "what did we decide?"` bypasses routing but still applies the registered contract and capability policy.

## Failure Modes

Missing credentials, package/import failures, invalid registry files, unavailable MCP servers, invalid structured output, and local database permissions can fail a run.

## Security Boundaries

Credentials enable model/provider calls but do not widen tool policy. Runtime-recorded artifacts, file changes, tests, and tool calls replace model assertions before results are trusted.

## Tests

The suite can validate registry, routing, contracts, policy, and deterministic tools offline. End-to-end model execution is credentialled and should be reported separately.

## Recovery

Run `doctor`, inspect MCP permissions and sessions, correct configuration, and retry. Export a session before destructive deletion.

## Known Limitations

The SDK depends on OpenAI Agents for live inference. Offline passing tests do not prove provider availability, model quality, or MCP credentials; maintenance definitions are not loaded by `RuntimeRegistry`.
