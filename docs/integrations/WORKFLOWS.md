# Durable Workflows

## Purpose

The workflow layer coordinates integration steps while persisting enough state and evidence to prevent duplicate outward effects and resume after process restart.

## Architecture

`workflow_runs` is unique by tenant, workflow ID, and idempotency key. `workflow_steps` records completed step evidence, and `workflow_events` records accepted and delivered milestones. The implemented workflow is `stock-to-offer-v1`.

## Configuration

Provide one `IntegrationDatabase`, deterministic delivery provider, and configured `CommunicationGateway`. Callers inject a stable run ID, idempotency key, authority set, and current timestamp.

## Commands

```powershell
$env:PYTHONPATH='sdk/python/src'
& sdk/python/.venv/Scripts/python.exe -m pytest -q sdk/python/tests/test_integration_stock_to_offer.py --basetemp work/pytest-workflows
```

## Examples

Calling `run` twice with the same tenant and idempotency key returns the original result, regardless of the second proposed run ID. Webhooks are passed to `reconcile_delivery`; completion occurs only when all channel deliveries reach delivered-or-later states.

## Failure Modes

Normalization failure marks the run failed and raises. Pricing, delivery, consent, template, authority, and channel errors propagate. A crash after run creation leaves an empty result that a retry resumes using the persisted run ID.

## Security Boundaries

The workflow does not invent authority. `send_customer_message` is required, and approval-required messages need the exact `approve:<message_id>` grant. Tenant and idempotency values must come from a trusted orchestration boundary.

## Tests

The end-to-end test proves one run, one pair of deliveries, stable `ZAR 156.25` pricing, process restart, two distinct delivery webhooks, duplicate webhook suppression, and final completion.

## Recovery

Retry an incomplete run with the same idempotency key. Reconstruct services against the same SQLite path and continue webhook reconciliation. Investigate `workflow_steps`, `workflow_events`, and retained evidence before manually intervening.

## Known Limitations

There is no worker queue, lease, timeout scheduler, compensation engine, or multi-process locking protocol. Resume is deterministic for the implemented local path; live distributed execution remains deferred.
