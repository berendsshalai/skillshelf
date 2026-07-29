# Approval Binding

## Purpose

Approval binding prevents a human decision for one sensitive operation from authorising another.

## Architecture

Canonical JSON arguments, run ID, tool name, operation, authorised root, user and expiry are hashed
into the durable approval record. Resume recomputes and compares the digest before invoking the
runtime-owned tool wrapper.

## Configuration

Set an approval TTL appropriate to the workflow and supply a stable authenticated user identity
from the control plane. The CLI requires the same bound user for decisions.

## Commands

Use `skillshelf approvals inspect ID --json`, `approvals approve ID --user USER`,
`approvals reject ID --user USER`, and `runs resume RUN_ID`.

## Example

Approval for writing `docs/report.md` with one content digest cannot be reused after the path or
content changes, even within the same run.

## Security boundaries

Approvals are exact, expiring, run-scoped and one-time at resume. Repository-root containment is
checked again after approval to prevent link or reparse-point substitution.

## Failure modes

Mutation, wrong user, expiry, rejection, missing checkpoint and already-consumed approval all fail
closed and are recorded as governance events.

## Tests

Approval-resume tests cover every bound field, path substitution, expiry, cross-run reuse,
concurrent resume and interrupted-process recovery.

## Recovery

Reject or let the stale approval expire, then initiate a new call and review its exact arguments.
Never repair approval digests by hand.

## Known limitations

Local CLI identity is asserted by the caller. Cryptographically attested workforce identity is
available only through a host control-plane integration.
