# Codex Memory

Codex-facing persistent memory built around the pinned claude-mem Codex plugin, hooks, worker, SQLite, transcript watcher, and MCP retrieval workflow.

## Safety defaults

- Progressive retrieval instead of full-database injection.
- Project-scoped search.
- Secret redaction before storage/import.
- `<private>...</private>` exclusions.
- Telemetry and cloud sync expected off unless explicitly enabled.
- Backups/exports exclude `.env` and credentials.
- Mutating install, uninstall, force-import, and recovery actions are explicit.

## Quick start

```powershell
powershell -File scripts/install-memory.ps1
powershell -File scripts/install-memory.ps1 -Execute
powershell -File scripts/doctor-memory.ps1
```

The first command is a dry run. The second installs the pinned `claude-mem@13.12.4` Codex integration and backs up `~/.codex/config.toml`.

The default data directory is `%USERPROFILE%\.claude-mem` on Windows or `~/.claude-mem`. Override it with `CLAUDE_MEM_DATA_DIR` or the scripts’ `-DataDir`/`--data-dir` option.

## Data lifecycle

`backup` creates a directory snapshot with SHA-256 metadata. `export` creates a portable JSON container with per-file hashes and base64 payloads. Neither includes `.env`. `import` validates every hash and refuses overwrite without `-Force`/`--force`. `recover` refuses a healthy SQLite header unless forced.

See `references/operations.md` for exact rollback and corruption-recovery procedures.

## Provenance

Upstream: `https://github.com/thedotmack/claude-mem`  
Pin: `132b46343e60ecf4057c427736c57b08f7615dfe`  
Licence: Apache-2.0  
Vendored evidence: `../../vendor/memory/`
