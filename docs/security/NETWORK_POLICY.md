# Network Policy

## Purpose

The network policy limits which SkillShelf components may contact external systems and makes every
network dependency visible.

## Architecture

All HTTP activity flows through reviewed MCP or connector/provider adapters. URLs are parsed and
validated before use, redirects are bounded and revalidated, and calls emit redacted evidence.
Offline tests use loopback servers and the bundled stdio MCP provider.

## Configuration

Declare HTTPS base URLs, allowed operations, timeouts and environment-variable secret references.
Plain HTTP is allowed only for `localhost`, `127.0.0.1` and `::1`.

## Commands

Use `skillshelf doctor --deep --json`, `skillshelf mcp doctor`,
`skillshelf connector doctor ID`, and `skillshelf communications doctor --json`.

## Example

A connector configured with `http://api.example` fails validation; the same protocol is accepted
for an explicit loopback test server.

## Security boundaries

Adapters reject embedded credentials, unsafe schemes, link-local/cloud-metadata targets and
unbounded redirects. Provider TLS verification remains enabled.

## Failure modes

DNS, TLS, timeout, redirect-policy and circuit-breaker failures return typed non-zero results and
do not advance sync checkpoints.

## Tests

Connector and provider suites cover loopback allowance, public HTTP rejection, retry limits,
redirect validation, timeouts, circuit breaking and redaction.

## Recovery

Correct the endpoint or trust configuration and run a non-mutating doctor/test before retrying a
workflow. Do not disable certificate validation.

## Known limitations

Host firewall and DNS policy are deployment responsibilities. SkillShelf validates application
configuration but does not replace operating-system egress controls.
