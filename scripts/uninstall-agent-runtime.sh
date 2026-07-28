#!/usr/bin/env sh
set -eu
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
TARGET="$ROOT/sdk/python/.venv"
if [ "${1:-}" != "--execute" ]; then printf 'Dry run: would remove %s\n' "$TARGET"; exit 0; fi
case "$TARGET" in "$ROOT"/*) rm -rf -- "$TARGET";; *) echo "Unsafe target" >&2; exit 2;; esac
printf '%s\n' "Removed isolated runtime only; local state and Codex configuration were preserved."
