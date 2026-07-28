# SkillShelf handoff

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
