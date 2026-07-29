# Provider Webhooks

## Purpose

Webhook handling authenticates provider events, rejects replays and reconciles delivery or
workflow state durably.

## Architecture

The ingress reads bounded raw bytes, verifies the provider signature before parsing, derives a
provider event ID, and atomically inserts an inbox record. A reconciler maps accepted events to
communication attempts and workflow events.

## Configuration

Configure webhook secret references, timestamp tolerance and connector/provider identity. Expose
the FastAPI endpoint only behind HTTPS and a request-size-limiting proxy.

## Commands

Provider callbacks use `/webhooks/{connector_id}`. Inspect resulting workflow state with
`skillshelf workflow status RUN_ID --json` and events with `skillshelf events tail --json`.

## Example

A Twilio callback is accepted only when its computed signature matches the request URL and form
fields; a duplicate provider event ID returns the existing inbox result.

## Security boundaries

Signature verification is constant-time, occurs before JSON/form interpretation, and uses the
external canonical URL configured by the operator. Raw secrets are never persisted.

## Failure modes

Missing/invalid signatures return 401, stale timestamps return 401, oversized requests return 413,
unknown providers return 404 and duplicate events are acknowledged idempotently.

## Tests

Provider contract tests cover valid/invalid Meta and Twilio signatures, replay, timestamp windows,
payload bounds, idempotency and state reconciliation.

## Recovery

Correct proxy canonical-URL configuration or rotate the secret reference, then request provider
redelivery. Do not manually insert unsigned events.

## Known limitations

SMTP delivery-status notifications are provider-specific and require a connector mapping; they are
not inferred from successful SMTP submission.
