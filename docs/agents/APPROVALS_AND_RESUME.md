# Approvals and Resume

## Purpose

SkillShelf interrupts sensitive tool calls, binds a human decision to the exact call, and resumes
the original durable run without repeating completed work.

## Architecture

The approval store persists run, session, tool, canonical-argument digest, operation, authorised
root, user, expiry and status. A replay checkpoint references the pending call. Resume revalidates
the binding and continues through the runtime-owned tool wrapper.

## Configuration

Set the state root with normal SkillShelf settings. Approval records share the run ledger SQLite
database. Never copy approval rows between installations.

## Commands

Use `skillshelf approvals list|inspect|approve|reject` and
`skillshelf runs resume RUN_ID`. Approval and rejection require `--user`; sensitive proposal
operations additionally require `--yes`.

## Example

`skillshelf approvals approve approval-123 --user alice` authorises only the stored digest.
`skillshelf runs resume run-123 --json` then resumes the bound checkpoint.

## Security boundaries

Changed arguments, roots, users, operations, expired decisions and rejected decisions cannot be
reused. Approval does not grant a general capability and cannot authorise a different run.

## Failure modes

Missing checkpoints, stale bindings, terminal runs and mutated arguments return non-zero. The
original pending state remains inspectable.

## Tests

Approval tests cover interruption persistence, approve/reject, expiry, argument mutation,
cross-run reuse and one-time resume.

## Recovery

Reject an obsolete approval and initiate a new run with the intended arguments. Restore the run
ledger from backup only as a complete database; do not edit approval rows manually.

## Known limitations

Approval identity is supplied by the local control plane. Enterprise identity-provider attestation
is a host integration, not bundled.
