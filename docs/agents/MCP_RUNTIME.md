# MCP Runtime

## Purpose

The MCP runtime connects approved servers to the specialist that needs them and captures their
operational evidence.

## Architecture

Definitions support stdio, streamable HTTP, SSE and host adapters. The assignment context manager
connects, discovers, filters and prefixes tools before creating the specialist, then cleans up in
reverse order. The bundled fake stdio server provides an offline architectural proof.

## Configuration

Edit `mcp/registry.yml` for reviewed providers. Reference headers and environment variables by
name. Plain HTTP is accepted only for loopback endpoints.

## Commands

Use `skillshelf mcp list`, `skillshelf mcp doctor`, `skillshelf mcp tools SERVER`,
`skillshelf mcp permissions AGENT`, and `skillshelf doctor --deep`.

## Example

Deep doctor launches `mcp/fake-server/server.py`, discovers only `read_probe`, calls it, verifies
its digest and closes the stdio session.

## Security boundaries

Tool filters are applied after discovery, exposed names are prefixed, collisions fail, and MCP
writes pass through durable approval policy. Provider errors are redacted.

## Failure modes

Required startup, discovery, call and cleanup failures fail the run. Optional failures produce a
typed degraded assignment with its fallback.

## Tests

MCP tests cover all transports, filtering, collision handling, real stdio discovery/call/cleanup,
timeouts, approval policy and required/optional availability.

## Recovery

Run `skillshelf mcp doctor`, correct the command, URL or secret reference, and retry in a new run.
Invalidate the tool cache after provider upgrades.

## Known limitations

Remote server trust and availability remain external. Host adapters are operational only when the
embedding host supplies them.
