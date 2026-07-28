# Upstream difference

Pinned source: `thedotmack/claude-mem@132b46343e60ecf4057c427736c57b08f7615dfe`.

## Preserved

- Codex marketplace/plugin manifest model.
- Native five-stage hook lifecycle.
- MCP memory server declaration.
- `search -> timeline -> get_observations` retrieval contract.
- Worker, SQLite schema/migrations, transcript watcher, context builder, private-marker validator, Windows handling, and Codex tests as vendored evidence.

## Added

- Pre-storage/import secret redactor.
- Credential-excluding backup and portable export/import with SHA-256.
- Doctor, migration, corruption-recovery, and reversible install/uninstall wrappers.
- Explicit privacy-first policy: telemetry and cloud sync off unless enabled by the user.
- Operational evidence and rollback requirements.

## Not vendored

Compiled worker/UI bundles, modes unrelated to memory search, server-beta/Postgres/Redis/cloud-sync deployment, provider implementations, and development-only tooling. The pinned upstream submodule remains the transparent source for those optional surfaces.

## Known limitations

- Header validation is not a full SQLite `PRAGMA integrity_check`; use the upstream Bun/SQLite runtime for deep integrity checks.
- The redactor is defense in depth and cannot identify every secret format.
- Portable export is a full approved-file snapshot, not a selective semantic export.
- Installing the runtime requires network access to the pinned npm package unless an already verified local marketplace is used.
