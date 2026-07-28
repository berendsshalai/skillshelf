# Runtime Specialists

## Purpose

The five specialists provide bounded expertise without turning every task into a full multi-agent run.

## Architecture

Find Skills handles discovery; Superpowers handles software methodology; Memory retrieves selected project history; Design Intelligence handles frontend design; Skill Governor stages governed improvements. Together with the master they form exactly six runtime definitions. Eight maintenance definitions remain opt-in and separate.

## Configuration

Each registry entry declares its skill, instruction, model profile, tool name, MCP allowlist, allowed/prohibited capabilities, turn limit, output contract, and token budget.

## Commands

```powershell
skillshelf agents --json
skillshelf agents inspect memory-agent --json
skillshelf run --agent superpowers-agent "diagnose the failing test" --json
```

## Examples

Use `memory-agent` for a prior decision, `find-skills-agent` for comparison without installation, and `skill-governor-agent` to stage—not apply—a reusable improvement.

## Failure Modes

Unknown IDs, missing skills, invalid MCP policy, prohibited operations, exhausted budgets, or invalid structured results stop execution. A specialist can report blocked or partial status.

## Security Boundaries

Specialists receive concise briefs and least-privilege tools. Discovery cannot install or star; memory cannot dump the database; governance cannot mutate live skills; implementation cannot publish without verification. Runtime-recorded execution is evidence; model claims and findings are interpretation.

## Tests

Registry validation checks exactly five specialist entries. Routing, delegation, safety, and output-contract tests exercise selection and bounded results.

## Recovery

Inspect the agent definition and MCP permissions, correct registry drift, then retry. Escalate cross-domain or ambiguous work to the master.

## Known Limitations

Offline construction proves definitions and policy, not credentialled model competence. Maintenance definitions are deliberately excluded from `skillshelf agents`.
