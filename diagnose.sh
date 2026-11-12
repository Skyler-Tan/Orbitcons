#!/usr/bin/env bash
set -u

APP="$HOME/.local/opt/cozy-orbit"
PY="$APP/.venv/bin/python"
LOG="${XDG_STATE_HOME:-$HOME/.local/state}/cozy-orbit/last-run.log"

echo "Cozy Orbit diagnostic — $(date -Is)"
echo "Session: ${XDG_SESSION_TYPE:-unknown}; Qt override: ${QT_QPA_PLATFORM:-default}"

if [[ -x "$PY" ]]; then
    echo "Python: $("$PY" --version 2>&1 || true)"
    echo "PySide6: $("$PY" -c 'import PySide6; print(PySide6.__version__)' 2>&1 || true)"
else
    echo "Python environment: missing ($PY)"
fi

echo "Commands:"
for cmd in nmcli bluetoothctl wpctl pactl brightnessctl systemsettings; do
    printf "  %-16s %s\n" "$cmd" "$(command -v "$cmd" || echo missing)"
done

echo
echo "Recent app log:"
tail -n 80 "$LOG" 2>/dev/null || echo "No app log yet."

echo
echo "Retry with platform diagnostics:"
echo "  QT_LOGGING_RULES='qt.qpa.*=true' $APP/launch.sh"
echo "X11 fallback, only if XWayland is available:"
echo "  QT_QPA_PLATFORM=xcb $APP/launch.sh"
