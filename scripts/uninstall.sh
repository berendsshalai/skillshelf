#!/usr/bin/env sh
set -eu
scope="${1:-project}"
if [ "$scope" = "user" ]; then target="${SKILLSHELF_TARGET_ROOT:-$HOME/.agents/skills}"; else target="${SKILLSHELF_TARGET_ROOT:-$PWD/.agents/skills}"; fi
for name in find-skills-codex superpowers-codex codex-memory codex-design-intelligence codex-skill-governor; do
  [ ! -e "$target/$name" ] || rm -rf "$target/$name"
done
printf 'Removed SkillShelf-owned skills from %s; unrelated skills were preserved.\n' "$target"
