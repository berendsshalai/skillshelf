# Specialist Connectivity

## Purpose

This document explains how SkillShelf resolves every declared specialist capability to a
function tool, MCP provider, or explicit degraded provider.

## Architecture

`agents/registry.yml` is validated before agent construction. The capability resolver returns
a provider and tool set for each declaration, while the MCP assignment service creates only the
servers allowed for the selected specialist. Required failures stop construction; optional
providers produce a typed degraded record. The run ledger records assignments, discovered tools,
calls and cleanup.

## Configuration

Configure MCP transports in `mcp/registry.yml`. Use environment-variable references, never
literal secrets. Host adapters are supplied by the embedding application and must declare their
available tools.

## Commands

Use `skillshelf agents inspect AGENT`, `skillshelf mcp permissions AGENT`,
`skillshelf mcp tools SERVER`, and `skillshelf doctor --deep --json`.

## Example

`skillshelf mcp permissions memory-agent` shows the project-memory provider and its filtered
read-only tools.

## Security boundaries

Assignments are per specialist, tool allow/deny filters are enforced after discovery, and an MCP
write still requires an exact durable approval. Specialists cannot call one another directly.

## Failure modes

Unknown capabilities and unavailable required MCP servers fail closed. Optional servers report
their fallback and limitation. Timeouts and cleanup errors are persisted against the run.

## Tests

The core-runtime, MCP operational and agent-graph suites cover strict resolution, filtering,
invocation, required/optional failures and cleanup.

## Recovery

Correct the registry or provider configuration and start a new run. Inspect the failed run and
events before replay; outbound effects are never replayed automatically.

## Known limitations

Host-provided browser and GitHub adapters depend on the host session. The local memory fallback is
keyword-based when the optional upstream MCP process is unavailable.
