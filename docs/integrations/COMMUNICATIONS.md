# Communications

## Purpose

The communication gateway proves consent-aware, authority-gated, idempotent customer messaging and asynchronous delivery reconciliation.

## Architecture

`MessageIntent` references an approved template and consent record. `CommunicationGateway` validates purpose, customer, channel, verification, consent expiry, workflow authority, exact approval, and intent expiry. Channel adapters return provider references; webhook receipts deduplicate provider events.

## Configuration

Configure named templates and adapters for each channel. The deterministic proof uses `MockChannelAdapter` for email and WhatsApp with non-empty sender identities. Store explicit consent before sending.

## Commands

```powershell
$env:PYTHONPATH='sdk/python/src'
& sdk/python/.venv/Scripts/python.exe -m pytest -q sdk/python/tests/test_integration_delivery_communications_rag.py --basetemp work/pytest-comms
```

## Examples

Send with `{"send_customer_message"}` and, when required, `{"approve:<message_id>"}`. Provider acceptance is recorded separately from delivery. Reconcile each returned provider reference with a unique event ID.

## Failure Modes

Missing or expired consent, unverified recipients, purpose/channel mismatch, missing authority or approval, expired intents, unknown templates, absent sender configuration, unknown provider references, and database failures fail closed.

## Security Boundaries

Consent does not imply authority, and authority does not replace consent. Exact message approval prevents a broad approval from authorizing unrelated content. Templates constrain rendered content, but caller-provided variables must still be treated as untrusted data.

## Tests

Tests prove two-channel acceptance, exact approval enforcement, consent checks, provider-delivered transitions, and duplicate webhook suppression.

## Recovery

Retry `send` with the same message ID; existing message/channel deliveries are reused. Replay a webhook with its original event ID safely. Correct consent or configuration before retrying policy failures.

## Known Limitations

Email and WhatsApp adapters are deterministic mocks. There is no live provider credential, recipient address field, signature verification, unsubscribe ingestion, attachment support, content escaping, retry queue, or delivery polling. Live sends remain deferred.
