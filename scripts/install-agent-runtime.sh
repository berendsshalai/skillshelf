#!/usr/bin/env sh
set -eu
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
SDK="$ROOT/sdk/python"
VENV="$SDK/.venv"
if [ ! -d "$VENV" ]; then python3 -m venv "$VENV"; fi
"$VENV/bin/python" -m pip install --disable-pip-version-check -r "$SDK/requirements.lock"
"$VENV/bin/python" -m pip install --disable-pip-version-check --no-deps -e "$SDK"
"$VENV/bin/python" "$ROOT/scripts/generate-agents.py"
"$VENV/bin/python" "$ROOT/scripts/validate-agents.py"
"$VENV/bin/python" "$ROOT/scripts/run-agent-smoke-tests.py"
printf '%s\n' "Installed without model calls, API-token use, reviews, or engagement actions."
printf '%s\n' "$VENV/bin/skillshelf doctor"
