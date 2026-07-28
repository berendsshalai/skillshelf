---
name: codex-memory
description: Persistent, privacy-bounded cross-session project memory for Codex. Use when Codex needs to recall prior decisions, sessions, observations, file changes, or project history; search memory progressively; install, diagnose, back up, export, import, migrate, recover, or uninstall the memory service; or enforce memory privacy, secret redaction, retention, and project isolation.
---

# Codex Memory

Preserve the audited claude-mem Codex path. Do not replace its storage, worker, transcript, hook, or MCP pipeline with an untested parallel system.

## Core workflow

1. Establish the current project root. Never search every project unless the user explicitly requests cross-project recall.
2. Redact secrets before storage. Treat `<private>...</private>` as an explicit exclusion, not the only control.
3. Retrieve progressively:
   - call `search` with project and narrow filters;
   - filter compact results by relevance;
   - call `timeline` only around useful anchors;
   - batch `get_observations` for selected IDs;
   - synthesize only the evidence needed for the answer.
4. State what memory was used and distinguish recalled evidence from inference.
5. Never inject the database, a whole corpus, or unfiltered session history into context.

Use the upstream memory MCP tools when installed. If MCP/vector search is unavailable, use SQLite/keyword fallback and report the degraded mode; do not invent results.

## Privacy boundary

- Never store credentials, access or refresh tokens, passwords, private keys, cookies, authorization headers, MFA/recovery codes, or connection strings.
- Apply `scripts/redact-secrets.*` before importing transcripts or manually adding memory.
- Honor private markers and project exclusion globs.
- Default telemetry off in SkillShelf deployments. Cloud sync remains off until the user explicitly configures it.
- Exclude `.env` and credential material from backups and exports.
- Keep memory out of `AGENTS.md` when native Codex hooks are active. Legacy tagged injection is a compatibility mode only.

Read [references/privacy.md](references/privacy.md) before changing capture, storage, export, sync, or telemetry behavior.

## Operations

Run PowerShell scripts on Windows and `.sh` wrappers elsewhere. All wrappers call portable Node code.

- Install dry run: `powershell -File scripts/install-memory.ps1`
- Install: `powershell -File scripts/install-memory.ps1 -Execute`
- Doctor: `powershell -File scripts/doctor-memory.ps1`
- Backup: `powershell -File scripts/backup-memory.ps1 -Output <directory>`
- Export: `powershell -File scripts/export-memory.ps1 -Output <file.json>`
- Import: `powershell -File scripts/import-memory.ps1 -InputFile <file.json>`
- Migrate: `powershell -File scripts/migrate-memory.ps1 -From <legacy-dir>`
- Recover: `powershell -File scripts/recover-memory.ps1 -InputFile <file.json> -Force`
- Uninstall dry run: `powershell -File scripts/uninstall-memory.ps1`
- Uninstall: `powershell -File scripts/uninstall-memory.ps1 -Execute`

Install/uninstall deliberately require `-Execute`/`--execute` because they mutate user Codex configuration. They create a timestamped `config.toml` backup first. Read [references/operations.md](references/operations.md) before destructive recovery, import with force, or uninstall.

## Retrieval selection

Read [references/retrieval.md](references/retrieval.md) for filters, timeline use, batching, token-cost reporting, and fallback behavior.

## Architecture and upstream

Read [references/architecture.md](references/architecture.md) when modifying installation, hooks, worker lifecycle, MCP declarations, transcript ingestion, schema, or context injection.

The pinned upstream evidence is under `../../vendor/memory/`. Verify it with `../../vendor/memory/MANIFEST.sha256`. Do not modify vendored files; adapt in this skill package and record the difference in `UPSTREAM_DIFF.md`.

## Completion checks

Before claiming a memory operation succeeded:

1. Run doctor.
2. Verify the database header or import hashes.
3. Verify project scoping and privacy exclusions.
4. Confirm the worker/MCP path or name the fallback.
5. Report changed paths, backup location, and recovery command.
