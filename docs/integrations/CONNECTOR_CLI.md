# Connector CLI

## Purpose

The connector CLI onboards, validates, probes and synchronises provider-neutral REST connectors.

## Architecture

A durable registry stores validated manifests separately from secret values. The service resolves
named operations into the safe REST connector, which supplies pagination, checkpoints, ETags,
retry-after handling, circuit breaking, idempotency and redacted evidence.

## Configuration

Define base URL, operations, pagination, mappings and environment-variable secret references in a
manifest. HTTP is limited to loopback; production endpoints require HTTPS.

## Commands

Use `skillshelf connector list|inspect|add|test|doctor|sync|import-openapi`.
Machine-oriented commands accept `--json`; adding or importing reviewed configuration requires
explicit file input.

## Example

`skillshelf connector test stock --json` performs the manifest's harmless probe operation and
records status, latency and a redacted response summary.

## Security boundaries

Secrets are never stored in manifests or output. Test cannot select a mutating operation. Sync is
bounded by resource, page and record limits and writes through canonical data services.

## Failure modes

Invalid schemas, missing secret references, unsafe URLs, rate limits and circuit-open states return
non-zero with retry information. A checkpoint advances only after durable persistence.

## Tests

Connector tests use loopback HTTP to prove test, pagination, incremental sync, ETag, retry-after,
circuit breaking, redaction and idempotency.

## Recovery

Inspect the connector, correct its manifest or secret reference, wait for retry-after/circuit
cooldown, and resume from the last committed checkpoint.

## Known limitations

Provider-specific OAuth exchanges are host responsibilities. SkillShelf bundles generic REST and
documented communication-provider adapters, not every vendor API.
