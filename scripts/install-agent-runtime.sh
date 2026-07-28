#!/usr/bin/env sh
set -eu
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
SDK="$ROOT/sdk/python"
VERSION=$(tr -d '\r\n' < "$ROOT/VERSION")
DATA_ROOT=${XDG_DATA_HOME:-"${HOME}/.local/share"}
VENV="${SKILLSHELF_INSTALL_ROOT:-$DATA_ROOT/skillshelf/runtime/$VERSION}/venv"
python3 -c 'import sys; raise SystemExit(0 if sys.version_info >= (3,11) else 2)' ||
  { echo "SkillShelf requires Python 3.11 or newer" >&2; exit 2; }
EXPECTED=$(awk '{print $1}' "$SDK/requirements.lock.sha256")
ACTUAL=$(python3 -c 'import hashlib,sys; print(hashlib.sha256(open(sys.argv[1],"rb").read()).hexdigest())' "$SDK/requirements.lock")
[ "$EXPECTED" = "$ACTUAL" ] || { echo "Dependency lock integrity verification failed" >&2; exit 2; }
if [ ! -d "$VENV" ]; then python3 -m venv "$VENV"; fi
"$VENV/bin/python" -m pip install --disable-pip-version-check -r "$SDK/requirements.lock"
WHEEL_ROOT=$(mktemp -d)
trap 'rm -rf -- "$WHEEL_ROOT"' EXIT
"$VENV/bin/python" -m pip wheel --disable-pip-version-check --no-deps --wheel-dir "$WHEEL_ROOT" "$SDK"
WHEEL=$(find "$WHEEL_ROOT" -maxdepth 1 -name "skillshelf_agents-${VERSION}-*.whl" -print -quit)
[ -n "$WHEEL" ] || { echo "SkillShelf wheel build failed" >&2; exit 2; }
"$VENV/bin/python" -m pip install --disable-pip-version-check --no-deps --force-reinstall "$WHEEL"
"$VENV/bin/python" "$ROOT/scripts/generate-agents.py" --profile runtime
"$VENV/bin/python" "$ROOT/scripts/validate-agents.py"
"$VENV/bin/python" "$ROOT/scripts/run-agent-smoke-tests.py"
"$VENV/bin/skillshelf" doctor --deep
printf '%s\n' "Installed without model calls, API-token use, reviews, or engagement actions."
printf '%s\n' "$VENV/bin/skillshelf doctor"
