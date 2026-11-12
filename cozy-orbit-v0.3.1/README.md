# Cozy Orbit v0.3.1

Patched floating radial control widget for Kubuntu/KDE Plasma. The rendering path keeps one fixed-size, translucent QWidget for the lifetime of the process and never calls `setMask()` or `clearMask()`. The orbit animates through painting only; the widget is not resized during hover transitions.

## Install or update

Extract this directory, open a terminal in it, then run:

```bash
chmod +x install.sh
./install.sh
```

The installer updates `~/.local/opt/cozy-orbit/cozy_orbit.py`, preserves the existing virtual environment, and saves a timestamped copy of the old Python file before replacing it. It installs/updates PySide6 in that environment, adds an application-menu entry, and enables autostart. To launch manually, run `~/.local/opt/cozy-orbit/launch.sh`.

## Controls

- Hover over the flower orb to expand the radial menu; move away to collapse it.
- Drag the center orb to reposition it. The position is saved.
- Click Wi-Fi or Bluetooth to toggle; volume and brightness buttons adjust by 5%; battery shows the current percentage; Settings opens KDE System Settings.
- Right-click the widget for Quit.

System commands are optional and use `nmcli`, `bluetoothctl`, `pactl`, and `brightnessctl`; missing commands do not crash the app. Install dependencies as needed with `sudo apt install network-manager bluez pulseaudio-utils brightnessctl`. Battery reads `/sys/class/power_supply`.

## If it still fails

Run `~/.local/opt/cozy-orbit/diagnose.sh`. It prints session/runtime details and the recent app log. The launcher logs to `~/.local/state/cozy-orbit/last-run.log`. For Qt platform diagnostics:

```bash
QT_LOGGING_RULES='qt.qpa.*=true' ~/.local/opt/cozy-orbit/launch.sh
```

As a diagnostic fallback, try `QT_QPA_PLATFORM=xcb ~/.local/opt/cozy-orbit/launch.sh` when XWayland is installed/available. This selects Qt's XCB platform plugin; it is not required for normal operation.

## Crash fix notes

The reported stack ends in QtWayland's shared-memory backing-store flush path. Dynamic window masks are removed, as are animation-time geometry changes. The app uses ordinary QWidget painting with a fixed client area and disables the extra system-background clear pass. This avoids the prior trigger pattern, though the exact Qt/compositor/driver combination still needs confirmation on the affected Kubuntu machine.
