# Evidence Integrity

## Purpose

This document defines which claims SkillShelf may make about tools, files, tests and run outcomes.

## Architecture

Runtime wrappers create evidence before and after every tool call. File evidence includes
normalised path, before/after SHA-256, size and change state. Command evidence includes arguments,
exit code, bounded stdout/stderr artifacts and duration. Result merging overwrites model claims
with ledger-derived evidence references.

## Configuration

Evidence is stored below the configured SkillShelf state root. Output limits and redaction apply
before persistence. Artifact digests are always computed over the stored bytes.

## Commands

Use `skillshelf runs inspect RUN_ID`, `skillshelf runs artifacts RUN_ID`,
`skillshelf events inspect EVENT_ID`, and `skillshelf traces inspect TRACE_ID`.

## Example

A specialist may describe a patch, but `files_changed` remains empty unless a successful write
tool recorded an after-hash for that path.

## Security boundaries

Secrets are redacted before logging. Model output cannot invent tool-call IDs, file hashes or test
results. Evidence references are scoped to their run and trace.

## Failure modes

Timed-out and failed calls remain recorded with no success digest. Missing or malformed mechanical
evidence downgrades the related claim instead of being inferred from prose.

## Tests

Core runtime and agent-graph tests assert successful and failed calls, file hashes, test evidence,
merge precedence and unsupported-claim rejection.

## Recovery

Re-run the bounded tool or test to create new evidence. Keep the failed record; do not overwrite
historical evidence.

## Known limitations

SkillShelf proves observed local/runtime effects. It cannot independently prove an external
provider's internal processing beyond signed responses and returned identifiers.
