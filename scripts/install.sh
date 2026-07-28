#!/usr/bin/env sh
set -eu
scope="${1:-project}"
repo=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
if [ "$scope" = "user" ]; then target="${SKILLSHELF_TARGET_ROOT:-$HOME/.agents/skills}"; else target="${SKILLSHELF_TARGET_ROOT:-$PWD/.agents/skills}"; fi
mkdir -p "$target"
stamp=$(date +%Y%m%d%H%M%S)
for name in find-skills-codex superpowers-codex codex-memory codex-design-intelligence codex-skill-governor; do
  if [ -e "$target/$name" ]; then mkdir -p "$target/.skillshelf-backup-$stamp"; cp -R "$target/$name" "$target/.skillshelf-backup-$stamp/$name"; rm -rf "$target/$name"; fi
  cp -R "$repo/skills/$name" "$target/$name"
done
printf 'Installed five SkillShelf skills in %s\n' "$target"
