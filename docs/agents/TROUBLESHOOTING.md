# Agent Troubleshooting

## Purpose

This guide diagnoses registry, generation, credentials, MCP, routing, session, evidence, and proposal failures.

## Architecture

Failures may occur before inference, during execution of the six runtime definitions, in bounded tools, or in the eight opt-in maintenance definitions. Treat each boundary separately.

## Configuration

Confirm repository discovery, model variables, `OPENAI_API_KEY`, writable SkillShelf home, MCP policy, generated definitions, and tracing sensitivity.

## Commands

```powershell
skillshelf doctor --json
skillshelf mcp doctor
skillshelf agents --json
python scripts/generate-agents.py --check
```

## Examples

If offline tests pass but `ask` fails, inspect API credentials/provider access. If `doctor` finds six agents but a maintenance agent is absent, that is expected.

## Failure Modes

Common causes include registry drift, missing skill files, unknown agent IDs, absent credentials, denied MCP tools, invalid output, locked SQLite files, and budget exhaustion.

## Security Boundaries

Do not fix access failures by widening allowlists blindly. Redact secrets from diagnostics. Runtime-recorded execution is evidence; model diagnoses and claims remain interpretation.

## Tests

Run the smallest relevant offline test first, then the complete suite. Run credentialled smoke tests only after deterministic checks pass.

## Recovery

Regenerate derived files, restore valid configuration, retry transient services, export or recreate damaged sessions, and use explicit maintenance workflows for repository repair.

## Known Limitations

`doctor` checks configuration presence, not provider correctness or model quality. Offline success cannot certify live credentials, MCP services, or maintenance-agent behavior.
