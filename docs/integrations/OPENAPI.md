# OpenAPI and Transport Boundary

## Purpose

This document defines the current API boundary honestly: the integration capabilities are callable Python services, not a deployed HTTP API.

## Architecture

Pydantic models provide validated request and response contracts for connectors, pricing, delivery, communications, retrieval, suggestions, and stock-to-offer workflow execution. No FastAPI application, HTTP router, or generated OpenAPI document is present in the implemented stack.

## Configuration

Configure services directly with a SQLite path, connector manifest, environment secret store, delivery calendar, communication adapters, and approved templates. Transport authentication and public endpoint configuration are not applicable yet.

## Commands

```powershell
$env:PYTHONPATH='sdk/python/src'
& sdk/python/.venv/Scripts/python.exe -m pytest -q sdk/python/tests/test_integration_*.py --basetemp work/pytest-integrations
```

## Examples

Call `calculate_price`, `DeterministicDeliveryProvider.quote`, `CommunicationGateway.send`, `SQLiteKnowledgeBase.search`, or `StockToOfferWorkflow.run` from an application process. Pydantic `model_dump(mode="json")` provides transport-ready payloads.

## Failure Modes

Invalid request models raise Pydantic validation errors. Domain policy failures raise `ValueError`, `PermissionError`, `KeyError`, connector exceptions, or provider runtime errors. There is currently no HTTP status-code mapping.

## Security Boundaries

Do not expose these services directly to untrusted clients. A future transport adapter must authenticate tenants, construct authority sets server-side, enforce body limits, redact errors, rate-limit requests, and preserve idempotency keys.

## Tests

Integration tests exercise the service contracts in process. The connector test alone crosses an HTTP boundary, using a deterministic local fake server.

## Recovery

Domain operations backed by SQLite can be retried with their idempotency key. Transport recovery, client retry headers, and distributed tracing await an HTTP adapter.

## Known Limitations

There is no current OpenAPI JSON/YAML artifact and no live API server. Adding a framework dependency, routes, authentication middleware, and generated schema is deferred; deterministic local service proof must not be described as a deployed API.
