# Communication Providers

## Purpose

SkillShelf supplies live-ready adapters for SMTP email, Meta WhatsApp and Instagram, and Twilio
SMS and Voice while retaining deterministic mock adapters for tests.

## Architecture

The communication gateway validates authority, consent and exact approval before dispatch. Provider
adapters accept an injected transport, generate idempotency keys, parse provider identifiers and
return redacted evidence. Readiness checks never send a message.

## Configuration

SMTP uses host, port, TLS mode, username and environment-referenced password. Meta uses Graph base
URL, API version, account/phone identifiers and a token reference. Twilio uses account SID, sender
identifier and token reference.

## Commands

Use `skillshelf communications doctor --json` to inspect configuration. Actual sends occur only
through an authorised workflow or tool call, not through doctor.

## Example

A WhatsApp workflow supplies a consent reference and approved message intent; the adapter posts
the reviewed payload with a stable idempotency key and stores only the returned message ID.

## Security boundaries

Credentials and message bodies are redacted from logs. Recipients, channel and content digest are
approval-bound. TLS verification is on and cannot be disabled by a connector manifest.

## Failure modes

Authentication failures, provider rate limits and network timeouts return typed retryability.
Permanent recipient/content errors dead-letter the workflow step.

## Tests

Contract tests use injected HTTP and SMTP transports to verify request shape, TLS, idempotency,
redaction, rate limits and response parsing without real sends.

## Recovery

Correct the secret reference or provider configuration, verify consent, and explicitly retry the
workflow step. Provider dashboards remain the authority for delivery status.

## Known limitations

Credentials are not bundled. Twilio Voice creates outbound call requests but does not host custom
TwiML applications; configure an authorised callback URL.
