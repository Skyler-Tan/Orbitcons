#!/usr/bin/env bash
set -euo pipefail

APP="$HOME/.local/opt/cozy-orbit"
DESKTOP="$HOME/.local/share/applications/cozy-orbit.desktop"
AUTOSTART="$HOME/.config/autostart/cozy-orbit.desktop"

echo "This will remove the Cozy Orbit application files and its launch shortcuts."
echo "Your Cozy Orbit settings and diagnostic logs will be kept."
read -r -p "Continue? [y/N] " answer

case "$answer" in
    [yY]|[yY][eE][sS]) ;;
    *)
        echo "Uninstallation cancelled."
        exit 0
        ;;
esac

if [[ -d "$APP" ]]; then
    rm -rf -- "$APP"
    echo "Removed: $APP"
else
    echo "Application directory not found: $APP"
fi

rm -f -- "$DESKTOP" "$AUTOSTART"
echo "Removed application menu and autostart shortcuts (if present)."
echo
echo "Cozy Orbit has been uninstalled."
echo "Settings and logs were preserved."
echo "If you later want to remove those too, check:"
echo "  Settings: ~/.config/CozyOrbit/ (location depends on QSettings configuration)"
echo "  Logs:     ${XDG_STATE_HOME:-$HOME/.local/state}/cozy-orbit/"
