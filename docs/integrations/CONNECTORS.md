# Connectors

## Purpose

The connector runtime reads approved REST resources through a validated manifest. The local integration test proves the network path against a real loopback HTTP server without requiring external credentials.

## Architecture

`ConnectorManifest` declares hosts, resources, authentication, pagination, rate limits, retries, webhooks, operations, and risk. `EnvironmentSecretStore` resolves secret references at runtime. `RESTConnector` validates the destination and performs requests with `httpx`.

## Configuration

Declare every hostname in `allowed_hosts`, every operation in `read_operations` or `write_operations`, and every credential name in `secret_references`. Credentials are environment-variable references, never literal manifest values. Private hosts and HTTP require explicit constructor opt-ins intended for local testing.

## Commands

```powershell
$env:PYTHONPATH='sdk/python/src'
& sdk/python/.venv/Scripts/python.exe -m pytest -q sdk/python/tests/test_integration_connector.py --basetemp work/pytest-connectors
```

## Examples

Construct a `ConnectorManifest`, set its referenced environment variable, then call `RESTConnector.read("stock", updated_since="...")`. The result contains immutable item tuples, page and request counts, ETag state, and a `not_modified` flag.

## Failure Modes

Invalid manifests fail before I/O. Disallowed schemes, hosts, private addresses, user-info URLs, oversized payloads, response drift, pagination overflow, exhausted retries, and open circuits fail closed. HTTP 429 and transient 5xx responses are retried within policy.

## Security Boundaries

DNS results are checked for private, loopback, link-local, and reserved addresses unless local testing is explicitly enabled. Redirects are disabled. Authorization values are excluded from the request log. The connector cannot call an undeclared read operation.

## Tests

The local fake API test proves environment secret injection, log redaction, Retry-After handling, page-number pagination, `updated_since`, ETag caching, and 304 handling.

## Recovery

Retry a failed read after the circuit reset period or instantiate a fresh connector after correcting configuration. ETag state is process-local, so a restarted connector performs a full read unless the caller persists its own synchronization cursor.

## Known Limitations

OAuth declarations validate but token acquisition is deferred. Cursor and Link pagination are implemented but the deterministic proof exercises page-number pagination. Live SaaS credentials, webhook signature verification, and production connector manifests remain deferred.
