# Durable Workflow Engine

## Purpose

The workflow engine executes provider-neutral, restart-safe step graphs including the
stock-to-offer reference workflow.

## Architecture

Definitions contain typed steps and retry policy. SQLite stores runs, attempts, events,
checkpoints, schedules and dead letters. A worker claims due work transactionally; a scheduler
enqueues due definitions. Step handlers are registered code, not manifest-supplied code.

## Configuration

Register a reviewed workflow definition and handler set. Configure retry count, exponential delay,
timeouts and an idempotency key. Worker and scheduler limits are explicit CLI options.

## Commands

Use `skillshelf workflow list|inspect|run|status|approve|resume|retry|cancel|dead-letter`,
`skillshelf worker run`, and `skillshelf scheduler run`.

## Example

`skillshelf workflow run stock-to-offer-v1 --input request.json --idempotency-key order-42`
returns the durable run ID. Repeating the same key returns the same result.

## Security boundaries

Only registered handlers run. Outbound steps enforce consent and approval. Workers use leases to
avoid duplicate processing, and signatures are verified before webhook events enter a workflow.

## Failure modes

Retryable failures are scheduled with bounded backoff. Exhausted attempts enter the dead-letter
queue with evidence. Worker restarts release expired leases and continue from checkpoints.

## Tests

Workflow tests cover ordering, idempotency, retry, restart, approval pause/resume, cancellation,
dead-letter replay and stock-to-offer integration.

## Recovery

Inspect the run and dead-letter record, correct the dependency, then use explicit retry. Never edit
step rows manually or replay an outbound effect without its idempotency key.

## Known limitations

The bundled store is SQLite and intended for one deployment boundary. Distributed PostgreSQL
leasing remains a future deployment adapter.
