#!/usr/bin/env bash
set -euo pipefail
HERE="$(cd -- "$(dirname -- "$0")" && pwd)"
DEST="$HOME/.local/opt/cozy-orbit"
STAMP="$(date +%Y%m%d-%H%M%S)"
mkdir -p "$DEST"
if [[ -f "$DEST/cozy_orbit.py" ]]; then cp -p "$DEST/cozy_orbit.py" "$DEST/cozy_orbit.py.v03-backup-$STAMP"; fi
install -m 0644 "$HERE/cozy_orbit.py" "$DEST/cozy_orbit.py.new"
mv -f "$DEST/cozy_orbit.py.new" "$DEST/cozy_orbit.py"
install -m 0755 "$HERE/launch.sh" "$DEST/launch.sh"
install -m 0755 "$HERE/diagnose.sh" "$DEST/diagnose.sh"
if [[ ! -x "$DEST/.venv/bin/python" ]]; then python3 -m venv "$DEST/.venv"; fi
if ! "$DEST/.venv/bin/python" -c 'import PySide6' >/dev/null 2>&1; then
  echo "PySide6 is missing from the app environment. Trying pip (network access may be required)..."
  if ! "$DEST/.venv/bin/python" -m pip install PySide6; then
    echo "Could not install PySide6. Restore network access and rerun this installer, or install PySide6 into this venv manually." >&2
    exit 1
  fi
else
  echo "Using the existing PySide6 installation (offline update)."
fi
mkdir -p "$HOME/.local/share/applications" "$HOME/.config/autostart"
DESKTOP="$HOME/.local/share/applications/cozy-orbit.desktop"
cat > "$DESKTOP" <<EOF
[Desktop Entry]
Type=Application
Name=Cozy Orbit
Comment=Floating radial system controls
Exec=$DEST/launch.sh
Icon=preferences-desktop
Terminal=false
Categories=Utility;
EOF
chmod 0644 "$DESKTOP"
cp "$DESKTOP" "$HOME/.config/autostart/cozy-orbit.desktop"
echo "Installed Cozy Orbit v0.3.1 at $DEST"
echo "Launch from the application menu, or run: $DEST/launch.sh"
