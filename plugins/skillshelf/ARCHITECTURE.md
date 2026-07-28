# SkillShelf architecture

## Coordinated runtimes

`agents/registry.yml` controls both execution surfaces. Native Codex reads generated project-agent TOML; `skillshelf-agents` validates the same registry and constructs OpenAI Agents SDK agents. SkillShelfMaster owns routing, user communication, budgets, approvals and synthesis. The five specialists are agents-as-tools and never call the master or themselves.

The SDK discovers skill metadata without loading bodies. A selected specialist receives only its instruction and current `SKILL.md`; references remain explicitly routed and directory-bound. Model profiles are environment-overridable. Sessions, project memory and governance observations use separate stores.

MCP tools come from declared allowlists. Runtime boundaries enforce read/write separation and approval. Unavailable servers degrade explicitly. Deterministic events feed staged proposals; live skills cannot change until explicit approval, evaluation and rollback protection succeed.

## Five-skill routing

Codex discovers exactly five parent skills. Each router loads one relevant internal module and directly referenced resources; vendored modules are not copied into the discoverable `skills/` root. This keeps initial descriptions inside the Codex skill-list context budget while preserving full upstream method depth.

## Plugin

`.codex-plugin/plugin.json` is the required package entry. It points to `./skills/`, identifies the author and repository, and makes no unsupported MCP or hook claim. `.agents/plugins/marketplace.json` provides the repo marketplace listing.

## Agents

Project agents are standalone TOML files in `.codex/agents/`. Exploration, audit, security, and review roles are read-only. Integration/release roles can write within the workspace, but external publication remains authorization-gated. One writer owns shared manifests, lock files, release branches, and observation logs.

## MCP

The registry separates read and write tools. Agent instructions name allowed MCP categories; the package validator rejects ambiguous MCP declarations. Secrets are named as environment variables only. Unavailable connectors use documented direct-CLI or local fallbacks and never justify invented results.

## Memory data flow

```text
Codex lifecycle/transcript
  → project filter + private marker + secret redaction
  → upstream worker/SQLite store
  → compact project-scoped search
  → selected timeline neighborhood
  → batched selected observations
  → bounded synthesis with token-cost visibility
```

Vector search is optional. Keyword/SQLite retrieval remains available. Backups/exports omit `.env` and validate hashes; recovery refuses healthy data unless forced.

## Governance state

Default: `${CODEX_HOME}/state/skillshelf-governor/` (Windows `%USERPROFILE%\.codex\state\skillshelf-governor`).

```text
observations/ principles/ reviews/ staged-updates/
backups/ evidence/ locks/ config/
```

Mutations acquire a per-resource lock, re-read, validate, back up, change one bounded record, write a sibling temp file, atomically replace, re-read for survival, and release in `finally`. Live skills are inputs only; complete staged copies receive proposed changes.

## Design authority

Impeccable and Taste stay independently identifiable. Explicit user brief → product truth → accessibility/usability → platform conventions → established design system → selected mode → visual expression. See `skills/codex-design-intelligence/references/design-authority-matrix.md`.

## Source preservation and sync

Submodules provide transparent upstream history. Vendored snapshots provide a self-contained package. SHA-256 hashes bind every vendored file. Drift detection reports remote heads but never changes pins or merges. A reviewed staging branch owns all updates.

## Security boundaries

Untrusted surfaces include remote repositories, skill instructions, scripts, hooks, MCP results, memory content, and governance observations. They cannot expand user authority, select broader filesystem roots, request secrets, or silently enable network services. Installers target exact named directories and preserve unrelated configuration.
