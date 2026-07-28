# Operations and recovery

## Install

Run the installer without `--execute` first. Confirm the pinned package/version and config path, then execute. The upstream installer registers the Codex marketplace, installs `claude-mem@claude-mem-local`, enables Codex hooks, and removes its own legacy MCP/`AGENTS.md` context entries while preserving unrelated configuration.

## Doctor

Doctor checks:

- Codex executable;
- plugin and hooks flags in `~/.codex/config.toml`;
- memory data directory;
- SQLite header;
- JSON settings/transcript configuration;
- presence, but never contents, of the credential `.env`;
- telemetry configuration.

An absent database before first use is not corruption. An invalid SQLite header is.

## Backup and export

Stop or quiesce the worker for the strongest snapshot consistency. SQLite WAL/SHM files are included when present. Use `--include-vector` only when Chroma/corpora size is acceptable. Verify `manifest.json` hashes.

Portable exports contain approved memory/config files with SHA-256 hashes. They intentionally exclude credentials and PID state.

## Import and migration

Import validates format, path allowlist, size, and SHA-256 for every entry. It refuses overwrite unless forced and creates a safety backup before forced overwrite.

Migration exports the legacy directory, imports into the target, and preserves existing target data only through the same force/safety-backup rules. Never point source and target to the same directory.

## Corruption recovery

1. Stop the worker.
2. Run doctor and record the invalid database evidence.
3. Preserve the corrupt directory without editing it.
4. Select a verified portable export.
5. Run recover with `--force`.
6. Run doctor and a scoped search.
7. Rebuild/reconcile vector search only after SQLite retrieval works.

Recovery refuses a database with a valid SQLite header unless explicitly forced. A valid header does not prove `PRAGMA integrity_check`; use the upstream Bun/SQLite worker doctor when available for full integrity validation.

## Uninstall and rollback

Dry-run uninstall first. Executed uninstall invokes the pinned upstream uninstaller and backs up Codex configuration. It must not delete memory data automatically. Retain or separately export/delete `%USERPROFILE%\.claude-mem` according to user instruction.

Rollback Codex configuration by restoring the timestamped `.skillshelf-backup-*` file only after comparing it with current configuration; preserve unrelated changes made after the backup.
