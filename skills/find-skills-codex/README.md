# Find Skills Codex

This router preserves Vercel's search-before-reinvention workflow and adds immutable pinning, licence review, prompt/script inspection, Codex packaging checks, Windows commands, offline reports, and a no-blind-install rule.

Run:

```powershell
pwsh skills/find-skills-codex/scripts/inspect-skill.ps1 -Repository https://github.com/owner/repo -Commit <sha>
```

The script is read-only. It emits JSON; it does not install.
