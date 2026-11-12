#!/usr/bin/env bash
set -u
APP="$HOME/.local/opt/cozy-orbit"
echo "Cozy Orbit diagnostic — $(date -Is)"
echo "Session: ${XDG_SESSION_TYPE:-unknown}; Qt override: ${QT_QPA_PLATFORM:-default}"
echo "Python: $($APP/.venv/bin/python --version 2>&1 || true)"
echo "PySide6: $($APP/.venv/bin/python -c 'import PySide6; print(PySide6.__version__)' 2>&1 || true)"
echo "Commands: nmcli=$(command -v nmcli || echo missing), bluetoothctl=$(command -v bluetoothctl || echo missing), pactl=$(command -v pactl || echo missing), brightnessctl=$(command -v brightnessctl || echo missing)"
echo "Recent app log:"
tail -n 80 "${XDG_STATE_HOME:-$HOME/.local/state}/cozy-orbit/last-run.log" 2>/dev/null || echo "No app log yet."
echo
echo "Retry with platform diagnostics: QT_LOGGING_RULES='qt.qpa.*=true' $APP/launch.sh"
echo "X11 fallback, only if XWayland is available: QT_QPA_PLATFORM=xcb $APP/launch.sh"
