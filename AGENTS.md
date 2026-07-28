# SkillShelf repository guidance

Preserve upstream attribution and exact pinned source behavior. Do not edit files under `vendor/` except by replacing an entire verified snapshot from the matching `upstream/` commit and regenerating hashes. Do not edit submodules.

SkillShelf exposes exactly five directories under `skills/`. Internal upstream modules remain below `vendor/` and are loaded progressively by a router.

Before completion, run:

```powershell
python scripts/validate-package.py
python -m pytest -q
```

Use one writer per shared manifest, lock file, release branch, or governance log. Agents report task completed, files inspected, files changed, tests run, evidence, and unresolved risks.
