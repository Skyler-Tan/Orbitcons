# Cozy Orbit

**Cozy Orbit** is a lightweight floating desktop control widget for Linux, built with Python and PySide6. It places a compact radial control interface on the desktop for quick access to common system functions.

> **Project status:** v0.6.0 — early release. Developed and tested primarily on Kubuntu with KDE Plasma 6. Behaviour may differ on other desktop environments and Wayland compositors.

## Features

- Floating, frameless desktop interface.
- Expand and collapse from the centre control.
- Drag the centre to reposition the widget.
- Radial controls for Wi-Fi, Bluetooth, volume, battery, brightness and widget settings.
- Built-in widget settings, including available colour themes and rotation preferences.
- Right-click context menu.
- Preferences stored using Qt `QSettings`.
- Diagnostic script and application log to help troubleshoot issues.

The availability of individual system controls depends on your Linux distribution, desktop session, hardware and installed command-line utilities.

## Important: what Cozy Orbit is

Cozy Orbit is currently a **standalone desktop overlay application**. It is not yet a native KDE Plasma Plasmoid and does not appear as an applet embedded in the Plasma panel or desktop-widget management system.

## Supported environment

The initial target environment is:

- Kubuntu / Ubuntu-based Linux
- KDE Plasma 6
- Python 3
- PySide6
- Wayland or X11 (window movement and behaviour can vary by compositor)

Other Linux distributions and desktop environments may work, but have not been verified.

## Requirements

- Python 3
- Python virtual-environment support (`venv`)
- `pip`
- PySide6 (installed in the application's virtual environment by the installer)

Optional system utilities used by system controls:

| Utility | Purpose |
|---|---|
| `nmcli` | Wi-Fi status and control |
| `bluetoothctl` | Bluetooth status and control |
| `wpctl` | PipeWire volume control |
| `pactl` | PulseAudio-compatible volume fallback |
| `brightnessctl` | Screen brightness control |
| `systemsettings` | Opens KDE System Settings |

Some controls may require additional permissions or hardware support. Missing optional utilities do not necessarily prevent the widget from starting.

## Installation

Clone or download this repository, then open a terminal in the project directory.

```bash
chmod +x install.sh launch.sh diagnose.sh uninstall.sh
./install.sh
```

The installer places the application under:

```text
~/.local/opt/cozy-orbit/
```

It creates a Python virtual environment, installs PySide6 if it is not already available in that environment, and creates a KDE application-menu entry and an autostart entry.

**Internet access may be required** the first time PySide6 is installed. Existing virtual-environment dependencies are reused when available.

## Launching

After installation, launch Cozy Orbit from your application menu, or run:

```bash
~/.local/opt/cozy-orbit/launch.sh
```

Application output is recorded at:

```text
~/.local/state/cozy-orbit/last-run.log
```

If `XDG_STATE_HOME` is set, the log is stored under that directory instead.

## Diagnostics

From the repository directory, run:

```bash
./diagnose.sh
```

The diagnostic script reports the session type, Qt platform override, Python and PySide6 versions, availability of optional system commands, and the last 80 lines of the application log.

For additional Qt platform logging, try:

```bash
QT_LOGGING_RULES='qt.qpa.*=true' ~/.local/opt/cozy-orbit/launch.sh
```

If you are using Wayland and XWayland is available, you can test the X11 Qt backend with:

```bash
QT_QPA_PLATFORM=xcb ~/.local/opt/cozy-orbit/launch.sh
```

This is a troubleshooting option, not a guaranteed fix.

## Updating

Download or pull the latest repository version and rerun:

```bash
./install.sh
```

The installer backs up the existing `cozy_orbit.py` before replacing it. It also reuses the existing virtual environment when possible.

Keep a copy of your project directory and any local changes before updating.

## Uninstallation

Run the uninstaller from the project directory:

```bash
./uninstall.sh
```

The uninstaller asks for confirmation, removes the installed application and its application-menu/autostart entries, and **preserves user settings and diagnostic logs**.

## Configuration and privacy

Cozy Orbit stores widget preferences locally through Qt `QSettings`. It does not need an online account to run. Diagnostic output is stored locally in the user's state directory.

The exact QSettings file location depends on the organisation and application identifiers configured in the source code and the platform.

## Known limitations

- Wayland compositors control window movement and placement. Dragging and positioning can behave differently between desktop environments.
- Brightness control depends on supported hardware and system permissions.
- Wi-Fi, Bluetooth and audio controls depend on the corresponding system services and utilities.
- This release is a standalone PySide6 overlay, not a native Plasma widget.
- The project has been developed primarily for Kubuntu / KDE Plasma 6; broader compatibility still needs testing.

## Contributing

Bug reports, testing feedback and pull requests are welcome. When reporting an issue, please include:

1. Linux distribution and version.
2. Desktop environment and version.
3. Session type (`Wayland` or `X11`).
4. Output from `./diagnose.sh`.
5. Relevant lines from `~/.local/state/cozy-orbit/last-run.log`.

Please remove personal information from logs before sharing them publicly.

## License

Cozy Orbit is distributed under the MIT License. See [LICENSE](LICENSE).
