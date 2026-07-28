# Integration Data Model

## Purpose

The integration database preserves source evidence, canonical commerce records, quarantines, decisions, communications, webhook receipts, and workflow history in one local SQLite store.

## Architecture

`source_records` stores immutable, content-hash-deduplicated inputs. Category mappings authorize normalization into products, variants, inventory snapshots, and supplier prices. Separate tables retain quarantines, price decisions, delivery quotes, consent, messages, deliveries, webhook receipts, workflow runs, steps, and events.

## Configuration

Pass a filesystem path to `IntegrationDatabase`. Configure category mappings per tenant and source before normalization. Timestamps should be timezone-aware, currency codes uppercase, stock non-negative, and supplier prices positive.

## Commands

```powershell
$env:PYTHONPATH='sdk/python/src'
& sdk/python/.venv/Scripts/python.exe -m pytest -q sdk/python/tests/test_integration_data_pricing.py --basetemp work/pytest-data
```

## Examples

Call `map_category("tenant-a", "supplier-a", "electronics", "category-electronics")`, then `normalize_stock(...)`. A valid record returns linked Pydantic canonical objects; an invalid record returns `None` and records a quarantine reason.

## Failure Modes

Missing required fields, unmapped categories, negative stock, invalid price values, and schema validation errors quarantine the source record. SQLite constraint or filesystem errors propagate to the caller.

## Security Boundaries

Every source and mapping operation carries tenant identity. The caller must still authorize database path access and tenant selection. Payloads may contain sensitive business data; protect the SQLite file and backups at the operating-system boundary.

## Tests

Tests prove immutable raw deduplication, canonical product/variant/inventory/supplier persistence, unmapped or invalid data quarantine, and persisted pricing evidence.

## Recovery

Correct the source data or mapping and normalize a new content version. Raw evidence and quarantine history remain available for diagnosis. Copy or back up the SQLite file only while writes are quiescent or through SQLite-supported backup tooling.

## Known Limitations

The implementation is local SQLite, uses a single process connection, and has no migrations, retention policy, encryption layer, row-level authorization, or distributed concurrency strategy. The deterministic fixture is proof, not a production master-data feed.
