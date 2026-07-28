# Retrieval and Citations

## Purpose

The local knowledge base provides deterministic full-text retrieval with provenance and freshness metadata suitable for evidence-bearing answers.

## Architecture

SQLite stores document metadata and an FTS5 virtual table of section chunks. Ingestion sorts sections, splits on blank-line paragraphs, hashes canonical content, and replaces prior chunks for the document ID. Search orders by BM25 rank with stable document and section tie-breakers.

## Configuration

Provide a SQLite path plus document ID, source, version, effective timestamp, ingestion timestamp, and section mapping. Search requires a retrieval timestamp and optional result limit.

## Commands

```powershell
$env:PYTHONPATH='sdk/python/src'
& sdk/python/.venv/Scripts/python.exe -m pytest -q sdk/python/tests/test_integration_delivery_communications_rag.py --basetemp work/pytest-rag
```

## Examples

Ingest an operations manual section, then search `delivery business days`. Each result includes text, score, document ID, source, version, section, effective/ingested/retrieved timestamps, content hash, and freshness.

## Failure Modes

Invalid FTS query syntax and unavailable FTS5 support raise SQLite errors. Unknown terms return an empty list. Invalid timestamps or citation values fail Pydantic validation.

## Security Boundaries

Retrieval performs no tenant filtering or document authorization. Use a separate database per security domain or add trusted filtering before exposing results. Citations establish provenance, not truth or permission.

## Tests

The deterministic test proves ingestion, full-text search, section citation, stable content hash, and `current` freshness classification.

## Recovery

Reingest the same document ID to replace its chunks. Rebuild the knowledge SQLite file from authoritative documents if corruption occurs. Preserve source/version metadata when rebuilding.

## Known Limitations

There are no embeddings, semantic reranking, tenant ACLs, query escaping helper, incremental chunk version history, OCR, or live document connectors. The proof is local FTS5; production retrieval infrastructure is deferred.
