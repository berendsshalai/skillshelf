#!/usr/bin/env sh
set -eu
scope="${1:-project}"
if [ "$scope" = "user" ]; then target="${SKILLSHELF_TARGET_ROOT:-$HOME/.agents/skills}"; else target="${SKILLSHELF_TARGET_ROOT:-$PWD/.agents/skills}"; fi
for name in find-skills-codex superpowers-codex codex-memory codex-design-intelligence codex-skill-governor; do
  test -f "$target/$name/SKILL.md" || { printf 'Missing %s\n' "$name" >&2; exit 1; }
done
printf 'Doctor passed: five SkillShelf skills are present.\n'
