# Self-Improvement Governance

## Purpose

Self-improvement records observations and stages reviewable proposals without allowing autonomous mutation of live skills.

## Architecture

The runtime Skill Governor is one of five specialists within six runtime definitions. It can inspect evidence, run evaluations, and stage updates. The eight maintenance definitions can assist only when explicitly invoked. Proposal storage supports list, inspect, reject, approve, evaluate, and rollback-oriented governance.

## Configuration

Keep auto-review disabled by default. Configure governance paths and evaluation commands locally; approval requires explicit confirmation.

## Commands

```powershell
skillshelf improve
skillshelf proposals list --json
skillshelf proposals inspect <proposal-id>
skillshelf proposals approve <proposal-id> --yes
```

## Examples

A repeated failure may create an observation and staged patch. Approval runs tests before applying; no model can declare its own proposal accepted.

## Failure Modes

Missing proposal IDs, failed evaluations, absent confirmation, unsafe scope, or inconsistent journals prevent application.

## Security Boundaries

The governor cannot modify live skills, merge staged work, expand MCP permissions, or publish. Recorded execution evidence outranks model interpretation.

## Tests

Governance safety tests cover approval, path scope, rollback records, and denial. Credentialled model suggestions are optional inputs, not proof.

## Recovery

Reject unsafe proposals, inspect journals, rerun evaluations, or use the governed rollback mechanism. Restore source files from version control when necessary.

## Known Limitations

No autonomous learning loop exists. Quality of model-proposed improvements is unproven offline, and maintenance agents are not automatically scheduled.
