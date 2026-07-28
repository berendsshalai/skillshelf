# Codex Skill Governor

The governor turns reusable task evidence into reviewed, complete staged skill packages. It stores state outside ephemeral worktrees, separates governance observations from project memory, uses owned locks and atomic writes, rejects secrets and path escapes, and deliberately provides no live-skill installation command.

Quick check:

```powershell
python scripts/governor.py init
python scripts/governor.py doctor
python -m pytest tests/test_governor.py -q
```

Upstream methodology is preserved verbatim under `vendor/skill-governor/` and attributed under CC BY 4.0.
