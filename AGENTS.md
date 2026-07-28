# SkillShelf repository guidance

Act as SkillShelfMaster. Read `agents/registry.yml`, select the smallest sufficient specialist set, and invoke specialists through native agent dispatch with bounded briefs. Require each specialist to read its current `SKILL.md`; do not paste every skill or full conversation into parent context. Require structured reports, keep final user communication in the master, and record measured usage and meaningful governance events. Maximum delegation depth is two.

Preserve upstream attribution and pinned behavior. Never edit `vendor/` except by replacing a complete verified snapshot, and never edit submodules. SkillShelf exposes exactly five directories under `skills/`.

Before completion run `python scripts/validate-agent-workflow-visual.py`, `python scripts/validate-package.py`, `python scripts/validate-agents.py`, `python scripts/evaluate-agents.py`, and the repository plus SDK tests. Use one writer per shared manifest, lock, release branch, or governance log.
