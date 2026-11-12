#!/usr/bin/env bash
set -uo pipefail
APP="$HOME/.local/opt/cozy-orbit"
PY="$APP/.venv/bin/python"
LOG="${XDG_STATE_HOME:-$HOME/.local/state}/cozy-orbit/last-run.log"
mkdir -p "$(dirname "$LOG")"
if [[ ! -x "$PY" ]]; then echo "Missing Python environment. Re-run install.sh." >&2; exit 1; fi
exec "$PY" "$APP/cozy_orbit.py" "$@" >>"$LOG" 2>&1
