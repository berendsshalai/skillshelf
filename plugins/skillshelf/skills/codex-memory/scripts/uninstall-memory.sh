#!/usr/bin/env sh
set -eu
exec node "$(dirname "$0")/installer.mjs" uninstall "$@"
