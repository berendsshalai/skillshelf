# Architecture

## Audited Codex path

- Installer: `CodexCliInstaller.ts`, with Windows `codex.cmd` resolution.
- Plugin: Codex manifest declares skills, MCP, hooks, and write capability.
- Hooks: session start, prompt submit, pre-tool, post-tool, and stop.
- MCP: stdio Node launcher locates the installed plugin and starts the memory server.
- Worker: sessions, observation generation, search, timeline, settings, and HTTP API.
- Storage: local SQLite plus optional server/Postgres and Chroma paths.
- Transcripts: JSONL watcher normalizes Windows paths and maps Codex tool/session events.
- Context: project-scoped timelines, summaries, selected full observations, and token economics.

## Data flow

`Codex event -> native hook/transcript adapter -> privacy/redaction gate -> worker -> project-scoped SQLite -> optional vector index`

`question -> compact search -> candidate filter -> timeline -> batched detail -> bounded synthesis`

## Isolation

Project identity is derived from the working tree/project context. Server schemas enforce project/session relationships. Every retrieval request must still carry an explicit project scope; schema constraints do not protect an unscoped read.

## Compatibility

Native Codex hooks own context injection. Legacy transcript watches may update a tagged `AGENTS.md` block, but native-hook-backed watches suppress that write to avoid duplicate/stale context.

## Optional surfaces

Postgres/server runtime, Redis, Chroma, provider APIs, cloud sync, knowledge corpora, and telemetry are not required for the default local Codex workflow. Enable them independently and document their credentials, network boundary, fallback, retention, and deletion semantics.
