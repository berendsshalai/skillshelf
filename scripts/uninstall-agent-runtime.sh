#!/usr/bin/env sh
set -eu
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
VERSION=$(tr -d '\r\n' < "$ROOT/VERSION")
DATA_ROOT=${XDG_DATA_HOME:-"${HOME}/.local/share"}
INSTALL_ROOT=${SKILLSHELF_INSTALL_ROOT:-"$DATA_ROOT/skillshelf/runtime/$VERSION"}
TARGET="$INSTALL_ROOT/venv"
if [ "${1:-}" != "--execute" ]; then printf 'Dry run: would remove %s\n' "$TARGET"; exit 0; fi
if [ ! -e "$TARGET" ]; then printf '%s\n' "Runtime is already absent."; exit 0; fi
case "$TARGET" in "$INSTALL_ROOT"/*) rm -rf -- "$TARGET";; *) echo "Unsafe target" >&2; exit 2;; esac
printf '%s\n' "Removed isolated runtime only; local state and Codex configuration were preserved."
