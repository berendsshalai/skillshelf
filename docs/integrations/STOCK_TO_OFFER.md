# Stock-to-Offer

## Purpose

Stock-to-offer is the reference vertical slice proving source normalization, auditable pricing, delivery estimation, governed messaging, and durable webhook completion.

## Architecture

The workflow persists a run, normalizes one stock payload, calculates and persists a price decision, generates and persists a delivery quote, renders an approved offer template, sends through configured channels, and waits for external delivery events.

## Configuration

Configure a category mapping, effective pricing rule, deterministic delivery provider, email and/or WhatsApp adapters, `stock-offer-v1` template, verified consent, channel list, stable idempotency key, and `send_customer_message` authority.

## Commands

```powershell
$env:PYTHONPATH='sdk/python/src'
& sdk/python/.venv/Scripts/python.exe -m pytest -q sdk/python/tests/test_integration_stock_to_offer.py --basetemp work/pytest-stock-offer
```

## Examples

The fixture ingests a Field Radio costing `ZAR 100.00`, maps electronics, prices it at `ZAR 156.25`, quotes delivery, sends matching email and WhatsApp offers, restarts the process, and completes after both delivered webhooks.

## Failure Modes

Bad stock is quarantined and the workflow fails. Ineffective pricing, invalid delivery input, missing consent, template or sender configuration, insufficient authority, expired quote/message, and unknown webhook references stop progression.

## Security Boundaries

The workflow accepts only explicitly injected authority. It binds customer, purpose, consent reference, message ID, and channels. The idempotency key is tenant-scoped; upstream callers must authenticate tenant identity and prevent cross-tenant key reuse.

## Tests

The end-to-end test proves exact price, single durable run, two idempotent deliveries, stable results on duplicate execution, restart from the same SQLite file, webhook deduplication, and completion only after both channels deliver.

## Recovery

Retry the same input with the same idempotency key. Resume webhook processing against the persisted run ID. Inspect raw records, quarantine, step evidence, provider references, and events before any manual correction.

## Known Limitations

The input is one fixture record, adapters are mocks, delivery is deterministic, and no public API or job runner exists. Live stock feeds, carrier quotes, provider sends, signature verification, scheduling, and multi-node workflow execution are deferred.
