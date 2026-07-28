# Progressive retrieval

## Required sequence

1. `search(query, limit=20, project=<project>)`
2. Filter compact results using title, type, date, concept, and files.
3. `timeline(anchor=<id>, depth_before=3, depth_after=3, project=<project>)` when chronology changes interpretation.
4. `get_observations(ids=[...])` once for all selected IDs.
5. Synthesize, cite IDs/dates where useful, and stop.

Do not fetch full detail for every search result. Batch two or more IDs. A query with no useful results is evidence of absence in the searched scope, not proof that an event never happened.

## Filters

- `project`: always set for normal project recall.
- `type`: observations, sessions, or prompts.
- observation type/concept: narrow bug fixes, decisions, discoveries, features, and file changes.
- date range: use when the user supplies a period or recent behavior matters.
- file path: use for code-history questions.

## Token economy

Report compact-result count, selected-detail count, and approximate injected tokens when available. Keep the final synthesized context below the configured injection limit. The upstream semantic prompt injection default is off and, when enabled, defaults to five results.

## Degraded operation

If vector search is unavailable, use SQLite keyword/FTS search. If MCP is unavailable but the worker is healthy, use its documented local API. If neither is available, run doctor and explain that retrieval is unavailable; do not inspect raw databases with ad hoc writes.
