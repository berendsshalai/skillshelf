# Integration Deployment

## Purpose

This guide runs and verifies the deterministic local integration proof and states what is still required before production deployment.

## Architecture

The implemented stack is a Python package using Pydantic, `httpx`, and SQLite. Tests run in the SDK virtual environment with `sdk/python/src` on `PYTHONPATH` and repository-local pytest temporary directories.

## Configuration

Use Python 3.11 or newer and install SDK dependencies. Select writable SQLite paths outside source directories. Set connector secrets as environment variables referenced by manifests. Local HTTP/private-host opt-ins are test-only.

## Commands

```powershell
$env:PYTHONPATH='sdk/python/src'
& sdk/python/.venv/Scripts/python.exe -m pytest -q sdk/python/tests/test_integration_*.py --basetemp work/pytest-integrations
& sdk/python/.venv/Scripts/python.exe -m ruff check sdk/python/src/skillshelf_agents/connectors sdk/python/src/skillshelf_agents/data sdk/python/src/skillshelf_agents/pricing sdk/python/src/skillshelf_agents/delivery sdk/python/src/skillshelf_agents/communications sdk/python/src/skillshelf_agents/workflows sdk/python/src/skillshelf_agents/rag sdk/python/src/skillshelf_agents/suggestions
```

## Examples

For local evaluation, use temporary SQLite files, the loopback connector server from the test, deterministic delivery, and mock channels. Persist a workflow database across process restarts to verify recovery behavior.

## Failure Modes

Missing dependencies or `PYTHONPATH`, unwritable database paths, unavailable SQLite FTS5, absent environment secrets, invalid manifests, and Windows file locks can prevent startup or cleanup.

## Security Boundaries

Never enable private-host or insecure-HTTP connector options in production. Store secrets outside manifests, restrict SQLite filesystem permissions, encrypt backups, isolate tenants, authenticate any future API, verify live webhook signatures, and source authority server-side.

## Tests

The required local evidence is the four integration tests plus targeted Ruff checks. The suite proves deterministic behavior only; it does not constitute live-provider certification, load testing, penetration testing, or disaster-recovery validation.

## Recovery

Back up SQLite using supported SQLite backup procedures. Restore the database and retry workflows with original idempotency keys. Rotate compromised credentials outside the manifest and restart connector instances to clear in-memory secret and ETag state.

## Known Limitations

There is no container image, service supervisor, migration runner, production database, HTTP API, metrics exporter, distributed tracing, queue, secret manager integration, or live provider credential setup. Deployment beyond deterministic local proof is deferred until those controls are implemented and verified.
