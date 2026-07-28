# SkillShelf

SkillShelf is Sha-Lai Berends’ provenance-first, Codex-native shelf of five routed agent skills. It preserves complete, pinned open-source source slices and adds Codex packaging, Windows-safe operations, security boundaries, behavioral contracts, tests, agents, MCP policy, and a documentation site.

SkillShelf is a downstream integration and adaptation. It is not affiliated with or endorsed by OpenAI, Anthropic, Vercel, or any upstream author.

## What this repository is

- A public skills library and Codex plugin.
- A transparent pin ledger plus self-contained vendored source snapshots.
- A reusable eight-agent architecture with bounded delegation.
- A least-privilege MCP registry.
- A GitHub Pages documentation and socials site.
- A staged upstream-sync system that never auto-merges.

## Why it exists

Agent workflows are often copied without licences, compressed until their edge cases disappear, or installed from moving branches. SkillShelf makes lineage, semantic preservation, context economy, and safe adaptation part of the product.

## Codex first

The plugin uses current `.codex-plugin/plugin.json`, repository `.agents/skills/`, project `.codex/agents/*.toml`, and documented Codex plugin-marketplace conventions. Claude-specific hooks and commands are mapped explicitly instead of presented as Codex features.

## Five-skill architecture

1. `find-skills-codex` — verified discovery before reinvention.
2. `superpowers-codex` — brainstorming, planning, TDD, debugging, review, verification, and branch completion.
3. `codex-memory` — project-scoped, progressive cross-session memory.
4. `codex-design-intelligence` — separate Impeccable and Taste engines.
5. `codex-skill-governor` — evidence-led, staged skill improvement.

Detailed upstream modules remain below `vendor/`; only these five routers are discoverable.

## Installation

PowerShell, project scope:

```powershell
git clone --recurse-submodules https://github.com/berendsshalai/skillshelf
cd skillshelf
pwsh ./scripts/install.ps1 -Scope Project
pwsh ./scripts/doctor.ps1 -Scope Project
```

Cross-platform:

```sh
git clone --recurse-submodules https://github.com/berendsshalai/skillshelf
cd skillshelf
sh ./scripts/install.sh project
sh ./scripts/doctor.sh project
```

## Plugin installation

```powershell
codex plugin marketplace add https://github.com/berendsshalai/skillshelf
codex plugin add skillshelf@skillshelf
```

Start a new Codex task after installation. Plugin marketplace availability can depend on the active Codex surface and workspace policy.

## Local skill installation

Use `-Scope Project` to copy only the five skills into the current repository’s `.agents/skills/`. Existing SkillShelf destinations are timestamped before replacement.

## Global user skill installation

```powershell
pwsh ./scripts/install.ps1 -Scope User
```

This writes only the five named directories under `%USERPROFILE%\.agents\skills`.

## Development checkout

```powershell
git submodule update --init --recursive
python scripts/generate-vendor-manifest.py
npm run check
```

Python 3.11+, Node 22+, Git, and PowerShell 7 are recommended.

## Uninstall and rollback

```powershell
pwsh ./scripts/uninstall.ps1 -Scope Project
```

Uninstall removes only the five SkillShelf-owned directories. Restore a pre-install snapshot from `.skillshelf-backup-<timestamp>` when needed. Memory has separate dry-run-gated uninstall and recovery commands under `skills/codex-memory/scripts/`.

## Agent system

Eight project agents live in `.codex/agents/`: source audit, Codex migration, memory integration, design integration, MCP security, behavioral evaluation, code review, and release. Read-heavy roles are sandboxed read-only. Every role declares skill/tool boundaries and evidence output.

## MCP system

`mcp/registry.yml` records purpose, transport, authentication, read/write tools, confirmation, data scope, secret environment names, installation state, validation, and fallback. `mcp/policy.yml` denies undeclared tools and separates reads from writes. Examples never contain credentials.

## Memory architecture

The pinned claude-mem Codex path is the behavioral/runtime authority:

```text
compact search → candidate filtering → local timeline → batched selected observations → synthesis
```

SkillShelf adds pre-storage secret redaction, privacy-first defaults, retention/backup/export/import/recovery operations, and explicit degraded-mode reporting. It never injects the full database into context or duplicates memory in `AGENTS.md`.

## Design architecture

Impeccable owns context, mode, UX structure, accessibility, responsiveness, design-system consistency, audits, performance, and hardening. Taste owns anti-generic composition, expressive typography, variance, density, motion, image-first direction, and stylistic specializations. The user brief, product truth, accessibility, platform conventions, and existing design system outrank visual-expression rules.

## Governance architecture

The governor stores stable state under `${CODEX_HOME}/state/skillshelf-governor/` and performs lock → fresh read → backup → bounded staged mutation → atomic write → structural verification → survival verification → unlock. It never modifies live skills automatically and keeps governance observations separate from ordinary project memory.

## Source preservation

`upstream/` contains six Git submodules pinned to the release commits. `vendor/` contains only the source slices needed at runtime or for behavioral verification. `upstream-lock.json`, each skill’s `PROVENANCE.yml`, `THIRD_PARTY_NOTICES.md`, and `vendor-manifest.json` make preservation auditable.

## Upstream sources

- [vercel-labs/skills](https://github.com/vercel-labs/skills)
- [obra/superpowers](https://github.com/obra/superpowers)
- [thedotmack/claude-mem](https://github.com/thedotmack/claude-mem)
- [pbakaus/impeccable](https://github.com/pbakaus/impeccable)
- [leonxlnx/taste-skill](https://github.com/leonxlnx/taste-skill)
- [rebelytics/one-skill-to-rule-them-all](https://github.com/rebelytics/one-skill-to-rule-them-all)
- [personal socials source](https://github.com/berendsshalai/berendsshalai-project-systemtoportfolio)

## Licence and attribution

SkillShelf-authored integration code is MIT-licensed. Vendored files remain under their recorded upstream licences: MIT, Apache-2.0, or CC BY 4.0. Apache notices and CC BY attribution are retained. See `THIRD_PARTY_NOTICES.md`; do not relicense vendored work by inference from this repository’s root licence.

## GitHub Pages documentation

The static multi-route site is in `site/` and deploys at `https://berendsshalai.github.io/skillshelf/`. Build it with `python scripts/build-site.py`.

## Social links

The `/socials/` route preserves the exact seven destinations at personal-source commit `79dc09a…`: GitHub, LinkedIn, X, Facebook, Instagram, EasyEquities, and the portfolio website.

## Testing

```powershell
python scripts/validate-package.py
python -m pytest -q
node --test skills/codex-memory/tests/*.test.mjs
python -m pytest skills/codex-skill-governor/tests -q
python scripts/build-site.py
python scripts/build-plugin.py
```

Tests cover structure, frontmatter, provenance hashes, behavioral routing, agent declarations, MCP policy, secret patterns, site routes/metadata/social URLs, install/reinstall/doctor/uninstall preservation, memory operations, and governor concurrency.

## Security

No credentials, `.env` files, databases, browser sessions, or authentication artifacts belong in Git. Remote skills and MCP output are untrusted content. Global configuration changes are explicit, backed up, and reversible. See `SECURITY.md`.

## Updating from upstream

```powershell
python scripts/update-upstreams.py
```

The command reports new commits. Updates must happen on a staging branch, re-check licences, regenerate a complete vendor snapshot, run semantic-preservation/security tests, and receive review. Nothing auto-merges.

## Contributing

Read `CONTRIBUTING.md`. Contributions must retain attribution, explain semantic changes, update contracts/migration maps, and include tests. Do not submit generated provider mirrors or live user state.

## Roadmap

See `ROADMAP.md` for required follow-up, optional improvements, and experimental ideas. Mandatory gaps are reported as such, not hidden as “future enhancements.”
