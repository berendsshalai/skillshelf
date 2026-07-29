# SkillShelf 0.4.0 Handoff

## Release identity

- Canonical version: `VERSION` (`0.4.0`)
- Python distribution: `skillshelf-agents`
- Import package: `skillshelf_agents`
- CLI: `skillshelf`
- Runtime source: `agents/registry.yml`
- Normal runtime: one master plus five specialists
- Maintenance: eight separate opt-in definitions

Do not describe all fourteen definitions as one flat system. Do not edit versions independently; update `VERSION` and synchronize the checked release surfaces, then run:

```powershell
python scripts/validate-version.py
```

## Artifact boundaries

The Codex plugin installs five skills. The Python wheel installs the CLI and SDK runtime. Generated native-agent TOMLs provide Codex role definitions. The local integration modules and tests are part of the wheel source but do not constitute a deployed provider service.

Install the SDK runtime:

```powershell
./scripts/install-agent-runtime.ps1
skillshelf doctor --json
```

Install project-scoped skills:

```powershell
pwsh ./scripts/install.ps1 -Scope Project
pwsh ./scripts/doctor.ps1 -Scope Project
```

Install the plugin where the Codex surface supports it:

```powershell
codex plugin marketplace add https://github.com/berendsshalai/skillshelf
codex plugin add skillshelf@skillshelf
```

## Operational commands

```powershell
skillshelf agents --json
skillshelf agents inspect skill-governor-agent --json
skillshelf ask "Find a skill for accessibility testing" --json
skillshelf run --agent superpowers-agent "Diagnose the failing test" --json
skillshelf usage --last --json
skillshelf sessions list --json
skillshelf mcp doctor
skillshelf proposals list --json
python scripts/generate-agents.py --check
npm run check
```

`ask` and `run` require `OPENAI_API_KEY`. Registry inspection, generation checks, package validation, and deterministic tests can run offline.

## Verified local capability

The deterministic integration proof uses a real loopback HTTP server, local SQLite, fixed fixtures, and mock communication adapters. It covers connector safety/retries/pagination/ETag, immutable raw data, canonical records and quarantine, exact Decimal price `ZAR 156.25`, business-day delivery, consent/authority, mock email and WhatsApp, durable stock-to-offer restart, idempotent webhooks, cited FTS retrieval, and capability suggestions.

```powershell
$env:PYTHONPATH='sdk/python/src'
& sdk/python/.venv/Scripts/python.exe -m pytest -q sdk/python/tests/test_integration_*.py --basetemp work/pytest-integrations
```

The optional web extra supplies a limited FastAPI control plane. It validates/stores connector manifests and exposes local status, but live sync and HTTP workflow execution are intentionally not wired.

## Evidence and evaluation boundary

Runtime-recorded artifacts, file changes, test executions, and tool calls are evidence. Agent summaries, findings, quality judgments, and evaluator commentary are model interpretation. Offline evaluation success must not be reported as credentialled model success.

Deferred live work includes OpenAI model calls, upstream memory worker/MCP validation, external connector credentials, carrier rates, email/WhatsApp delivery, webhook signatures, and protected model-quality evaluation. No PostgreSQL deployment or generated OpenAPI artifact is part of 0.4.0.

## Verification sequence

```powershell
python scripts/validate-version.py
python scripts/validate-package.py
python scripts/generate-agents.py --check
python -m pytest -q
node --test skills/codex-memory/tests/*.test.mjs
python scripts/build-site.py
python scripts/build-plugin.py
```

Report actual results from the current checkout. Do not preserve historical pass counts as if they were newly measured.

## Recovery

For current 0.4.0 project installations:

1. Run `pwsh ./scripts/uninstall.ps1 -Scope Project`.
2. Restore the relevant `.skillshelf-backup-<timestamp>` directory.
3. For memory, run its dry-run uninstall/recovery command first and execute only after reviewing the reported target and backup.
4. Re-clone with submodules and check out the intended 0.4.0 release reference when one is published.

The old `v0.1.0` reconstruction instructions are historical and are not the current-release recovery path.

## Provenance and licensing

Preserve `upstream-lock.json`, every `PROVENANCE.yml`, `vendor-manifest.json`, and `THIRD_PARTY_NOTICES.md`. Upstream updates require a staging branch, licence review, complete snapshot regeneration, semantic/security tests, and human review. SkillShelf-authored MIT code does not relicense Apache-2.0 or CC BY 4.0 vendored material.
