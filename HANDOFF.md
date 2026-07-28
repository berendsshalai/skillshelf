# SkillShelf handoff

## Agentic runtime patch

- Branch: `codex/agentic-runtime`
- Python distribution: `skillshelf-agents` 0.2.0
- Import package: `skillshelf_agents`
- CLI: `skillshelf`
- Shared source: `agents/registry.yml`
- Native definitions: one master plus five generated Codex specialists
- SDK pattern: manager with specialists as tools and lazy dynamic skill instructions

Install:

```powershell
./scripts/install-agent-runtime.ps1
& ./sdk/python/.venv/Scripts/skillshelf.exe doctor
```

Offline commands do not require an API key. Model-backed `ask` and `run` require `OPENAI_API_KEY`. The installer does not call a model, enable auto-review, modify unrelated Codex configuration, or perform GitHub engagement.

Measured deterministic context comparison:

| Strategy | Estimated skill-file context |
|---|---:|
| Eager master with all five `SKILL.md` files | 4,223 tokens |
| Lazy selected specialist median | 734 tokens |

This bytes/4 measurement shows a 3,489-token reduction for skill-file context while all 5/5 deterministic routing fixtures pass. It is not a measurement of total paid model usage.

Runtime verification:

| Gate | Result |
|---|---|
| Registry and generated Codex agents | Passed |
| SDK unit/integration/safety tests | 22 passed |
| Repository tests | 34 passed |
| Memory Node tests | 9 passed |
| Routing evaluations | 5 passed |
| Ruff and strict mypy | Passed |
| Offline CLI/install smoke | Passed |
| Python wheel and plugin archive | Passed |
| MCP | Policy/permissions passed; optional live servers degrade as `SKIPPED` |
| Memory | Progressive integration present; live upstream worker not installed |
| Governance | Deterministic events, staging, approval and rollback tested |
| Star support | Explicit `--yes`, auth, idempotency and verification tested |

The SDK session database, Codex project memory and governor observations remain separate. Sensitive tracing is off by default. Auto-review is off and no proposal can mutate a live skill without explicit approval and passing evaluations.

## Project state

The complete release is at `C:\Users\User\Desktop\skillshelf` on branch `main`.

## Components

The repository contains the five routed skills, six pinned upstream submodules, seven-source lock including socials, self-contained vendor slices, eight Codex agents, MCP registry/policy/examples, safe installers, update tooling, test suite, static multi-route site, and release workflows.

## Installation

```powershell
codex plugin marketplace add https://github.com/berendsshalai/skillshelf
codex plugin add skillshelf@skillshelf
```

Repository scope:

```powershell
pwsh ./scripts/install.ps1 -Scope Project
pwsh ./scripts/doctor.ps1 -Scope Project
```

## Update

```powershell
python scripts/update-upstreams.py
```

Review drift on a staging branch; never merge it automatically.

## Known limitations

- Live end-to-end memory worker/MCP validation requires installing the pinned upstream claude-mem runtime in a disposable Codex profile. SkillShelf ships the audited integration evidence and privacy/operations layer, not the compiled worker bundle.
- Universal OpenAI Plugins Directory availability requires separate portal review and approval; publishing this GitHub repository does not imply directory approval.

## Verification

| Suite | Result |
|---|---|
| Package/schema/provenance/security validator | Passed |
| Python structural, behavioral, governor, site, and installation tests | 34 passed |
| Memory Node tests | 9 passed |
| Plugin creator validator | Passed |
| PowerShell syntax | Passed |
| Static site build | 11 required artifacts verified |
| Plugin archive | 328 files verified |
| Isolated Codex plugin install/reinstall/remove | Passed |
| Browser desktop/mobile overflow | 0 px overflow at 1440 and 320 widths |
| Browser socials | 7/7 secure cards, metadata and structured data passed |
| Browser console | 0 errors |

## Recovery

1. For project skills, run `pwsh ./scripts/uninstall.ps1 -Scope Project`.
2. Restore the relevant `.skillshelf-backup-<timestamp>` directory created beside the installed skills.
3. For memory, run the dry-run `pwsh ./scripts/uninstall-memory.ps1`, then repeat with `-Execute` only after checking the reported config backup.
4. Re-clone with `git clone --recurse-submodules` and check out tag `v0.1.0` to reconstruct the release.

## Release record

- Repository: `https://github.com/berendsshalai/skillshelf`
- Local path: `C:\Users\User\Desktop\skillshelf`
- Branch: `main`
- Commit: the annotated release reference `v0.1.0^{commit}` resolves the exact tested release commit
- Tag: `v0.1.0`
- GitHub Pages: `https://berendsshalai.github.io/skillshelf/`
- Test results: 34 Python + 9 memory tests passed; all build, schema, plugin, browser, and installation checks passed
- Upstream pins and licences: `upstream-lock.json` and `THIRD_PARTY_NOTICES.md`
