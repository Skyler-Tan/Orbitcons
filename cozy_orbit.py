#!/usr/bin/env python3
"""
Cozy Orbit v0.9.1
A customisable radial desktop control widget for KDE Plasma 6 (Wayland/X11).

Requirements:
    Python 3.10+
    PySide6
    NetworkManager (nmcli) for Wi-Fi
    BlueZ (bluetoothctl) for Bluetooth
    PipeWire (wpctl) or PulseAudio (pactl) for volume
    brightnessctl for brightness

Run:
    python cozy_orbit.py

User preferences are stored using QSettings.

What's new in 0.9.1:
    * Individual controls can be repositioned using their hover-arc handles.
    * Fractional pixmap drawing reduces icon jitter during orbit rotation.
    * Subtle hover feedback keeps the controls compact.

What's new in 0.9.0:
    * System commands run in background threads, so the widget never freezes
      while nmcli / bluetoothctl / brightnessctl are working.
    * Status polling and the animation timer only run while the orbit is open.
    * Rotation is time-based (same speed on any refresh rate / system load).
    * Volume and brightness show the real level after each change; volume is
      capped at 100% on PipeWire; right-click Vol -/+ to mute.
    * Wi-Fi / Bluetooth buttons dim when off; battery shows a charging bolt.
    * Sharp icons on HiDPI screens.
    * Remembers its position (X11), only one instance can run at a time,
      Escape closes the orbit, optional "Start at login", live theme preview.
    * Renamed the `palette` property (it shadowed QWidget.palette()).
"""

from __future__ import annotations

import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import (
    Qt, QPoint, QPointF, QRectF, QTimer, QEasingCurve,
    QPropertyAnimation, Property, QSettings, QLockFile, Signal,
)
from PySide6.QtGui import (
    QAction, QColor, QFont, QGuiApplication, QPainter, QPen, QBrush,
    QLinearGradient, QIcon, QPixmap,
)
from PySide6.QtWidgets import (
    QApplication, QWidget, QMenu, QDialog, QVBoxLayout, QHBoxLayout,
    QLabel, QComboBox, QSlider, QCheckBox, QDialogButtonBox,
    QFormLayout, QGroupBox, QMessageBox,
)

APP_NAME = "Cozy Orbit"
APP_VERSION = "0.9.1"
ORG_NAME = "CozyOrbit"
SETTINGS_DOMAIN = "cozy-orbit"

SIZE = 420
CENTER = QPointF(SIZE / 2, SIZE / 2)
ORB_RADIUS = 34
BUTTON_RADIUS = 26
ORBIT_RADIUS = 137
ICON_SIZE = 28
FRAME_INTERVAL_MS = 16
STATUS_INTERVAL_MS = 3000
DRAG_THRESHOLD = 8
# Radians per second for each speed level (level 2 ≈ one revolution / 2 min).
ROTATION_RAD_PER_SEC_PER_LEVEL = 0.027

LABELS = [
    "Wi-Fi", "Bluetooth", "Volume Down", "Volume Up",
    "Battery", "Brightness Down", "Brightness Up", "Settings",
]
# Prefer the active desktop icon theme (Breeze on KDE). Text fallbacks are
# used only when a theme does not provide one of these standard icon names.
SYSTEM_ICON_CANDIDATES = [
    ("network-wireless", "network-wireless-connected"),
    ("bluetooth", "bluetooth-active"),
    ("audio-volume-low", "audio-volume-medium"),
    ("audio-volume-high", "audio-volume-medium"),
    ("battery", "battery-full"),
    ("display-brightness-low", "display-brightness", "preferences-desktop-display"),
    ("display-brightness-high", "display-brightness", "preferences-desktop-display"),
    ("preferences-system", "settings-configure"),
]
ICON_FALLBACKS = ["W", "B", "−", "+", "%", "−", "+", "⚙"]

THEMES = {
    "Pastel Pink": {
        "background_start": "#FFF1F9", "background_end": "#E2D5FA",
        "petal_a": "#FFD3E3", "petal_b": "#DCCBFA",
        "button_a": "#FFD3E3", "button_b": "#DCCBFA",
        "center_start": "#FFE5EE", "center_end": "#E4D4FA",
        "accent": "#F7B8D0", "text": "#594563",
        "center_icon": "#916A9E", "outline": "#FFFFFF",
        "menu_bg": "#FFF5FA", "menu_text": "#594563",
        "menu_selected": "#E8D9F5",
    },
    "Lavender": {
        "background_start": "#F4EEFF", "background_end": "#DCD0F5",
        "petal_a": "#DCCBFA", "petal_b": "#C4A9EB",
        "button_a": "#DCCBFA", "button_b": "#C4A9EB",
        "center_start": "#F0E8FF", "center_end": "#CDB9F0",
        "accent": "#B99BE5", "text": "#514267",
        "center_icon": "#765D9B", "outline": "#FFFFFF",
        "menu_bg": "#F7F2FF", "menu_text": "#514267",
        "menu_selected": "#E5D9F7",
    },
    "Ocean Blue": {
        "background_start": "#EAF8FF", "background_end": "#C9E6F7",
        "petal_a": "#BFE7F5", "petal_b": "#BFCFF4",
        "button_a": "#BFE7F5", "button_b": "#BFCFF4",
        "center_start": "#E0F7FF", "center_end": "#C9DDF7",
        "accent": "#8ECDE5", "text": "#34566B",
        "center_icon": "#477D9B", "outline": "#FFFFFF",
        "menu_bg": "#F0FAFF", "menu_text": "#34566B",
        "menu_selected": "#D7EFF9",
    },
    "Mint Green": {
        "background_start": "#EEFFF7", "background_end": "#D0F0E2",
        "petal_a": "#C7F0DF", "petal_b": "#CDE8F5",
        "button_a": "#C7F0DF", "button_b": "#CDE8F5",
        "center_start": "#E5FFF3", "center_end": "#CBEDE0",
        "accent": "#9ADCC3", "text": "#3D6255",
        "center_icon": "#568A75", "outline": "#FFFFFF",
        "menu_bg": "#F2FFF9", "menu_text": "#3D6255",
        "menu_selected": "#D8F4E7",
    },
    "Dark": {
        "background_start": "#393347", "background_end": "#242333",
        "petal_a": "#78658E", "petal_b": "#5B668B",
        "button_a": "#78658E", "button_b": "#5B668B",
        "center_start": "#665477", "center_end": "#3F526F",
        "accent": "#B99BE5", "text": "#F4ECFA",
        "center_icon": "#FFFFFF", "outline": "#CFC3E2",
        "menu_bg": "#302B3B", "menu_text": "#F4ECFA",
        "menu_selected": "#514663",
    },
}


# ---------------------------------------------------------------------------
# Helpers (no Qt widgets involved, safe to call from worker threads)
# ---------------------------------------------------------------------------

def desktop_icon(candidates: tuple[str, ...]) -> QIcon:
    """Return the first icon available in the user's current desktop theme."""
    for name in candidates:
        icon = QIcon.fromTheme(name)
        if not icon.isNull():
            return icon
    return QIcon()


def is_wayland() -> bool:
    return QGuiApplication.platformName().lower().startswith("wayland")


def has_command(name: str) -> bool:
    return shutil.which(name) is not None


def run_command(args: list[str], timeout: float = 4.0):
    try:
        return subprocess.run(
            args, capture_output=True, text=True, timeout=timeout, check=False
        )
    except (OSError, subprocess.TimeoutExpired):
        return None


def get_output(args: list[str], fallback: str = "") -> str:
    result = run_command(args)
    if result and result.returncode == 0:
        return result.stdout.strip()
    return fallback


def launch_application(name: str, arguments: tuple[str, ...] = ()) -> bool:
    executable = shutil.which(name)
    if not executable:
        return False
    try:
        subprocess.Popen(
            [executable, *arguments], stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL, start_new_session=True,
        )
        return True
    except OSError:
        return False


def query_wifi() -> str:
    if not has_command("nmcli"):
        return "N/A"
    state = get_output(["nmcli", "radio", "wifi"], "unknown").lower()
    if state == "enabled":
        return "On"
    if state == "disabled":
        return "Off"
    return "Unknown"


def query_bluetooth() -> str:
    if not has_command("bluetoothctl"):
        return "N/A"
    result = run_command(["bluetoothctl", "show"])
    if result is None:
        return "Unknown"
    output = result.stdout.lower()
    if "powered: yes" in output:
        return "On"
    if "powered: no" in output:
        return "Off"
    if "no default controller" in output:
        return "N/A"
    return "Unknown"


def read_volume() -> str:
    """Human-readable current volume, e.g. 'Volume 45%' or 'Volume 45% (muted)'."""
    if has_command("wpctl"):
        out = get_output(["wpctl", "get-volume", "@DEFAULT_AUDIO_SINK@"])
        match = re.search(r"([\d.]+)", out)
        if match:
            pct = round(float(match.group(1)) * 100)
            return f"Volume {pct}%" + (" (muted)" if "MUTED" in out else "")
    elif has_command("pactl"):
        out = get_output(["pactl", "get-sink-volume", "@DEFAULT_SINK@"])
        match = re.search(r"(\d+)%", out)
        if match:
            muted = "yes" in get_output(["pactl", "get-sink-mute", "@DEFAULT_SINK@"]).lower()
            return f"Volume {match.group(1)}%" + (" (muted)" if muted else "")
    return "Volume changed"


def read_brightness() -> str:
    out = get_output(["brightnessctl", "-m"])
    fields = out.split(",")
    if len(fields) >= 4 and fields[3].endswith("%"):
        return f"Brightness {fields[3]}"
    return "Brightness changed"


def autostart_file() -> Path:
    config = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return config / "autostart" / "cozy-orbit.desktop"


def autostart_enabled() -> bool:
    return autostart_file().exists()


def set_autostart(enabled: bool) -> bool:
    path = autostart_file()
    try:
        if enabled:
            path.parent.mkdir(parents=True, exist_ok=True)
            script = Path(__file__).resolve()
            path.write_text(
                "[Desktop Entry]\n"
                "Type=Application\n"
                f"Name={APP_NAME}\n"
                "Comment=Radial desktop control widget\n"
                f'Exec="{sys.executable}" "{script}"\n'
                "Terminal=false\n"
                "X-KDE-autostart-after=panel\n"
            )
        else:
            path.unlink(missing_ok=True)
        return True
    except OSError:
        return False


@dataclass
class JobResult:
    ok: bool
    message: str
    permission_error: bool = False


# ---------------------------------------------------------------------------
# Settings dialog
# ---------------------------------------------------------------------------

class WidgetSettingsDialog(QDialog):
    """Preferences dialog for Cozy Orbit itself."""

    def __init__(self, settings: QSettings, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.setWindowTitle("Cozy Orbit — Widget Settings")
        self.setMinimumWidth(340)
        self.setModal(True)
        self.setAttribute(Qt.WidgetAttribute.WA_QuitOnClose, False)

        root = QVBoxLayout(self)
        intro = QLabel("Personalise the look and motion of your orbit.")
        intro.setWordWrap(True)
        root.addWidget(intro)

        appearance = QGroupBox("Appearance")
        appearance_form = QFormLayout(appearance)
        self.theme_combo = QComboBox()
        self.theme_combo.addItems(THEMES.keys())
        self.theme_combo.setCurrentText(
            settings.value("theme", "Pastel Pink", type=str)
        )
        # Connected after the initial value is set so opening the dialog
        # doesn't trigger a preview.
        self.theme_combo.currentTextChanged.connect(self.preview_theme)
        appearance_form.addRow("Colour theme", self.theme_combo)
        root.addWidget(appearance)

        motion = QGroupBox("Animation")
        motion_layout = QVBoxLayout(motion)
        self.rotate_check = QCheckBox("Rotate controls while the menu is open")
        self.rotate_check.setChecked(
            settings.value("rotation_enabled", True, type=bool)
        )
        motion_layout.addWidget(self.rotate_check)

        speed_row = QHBoxLayout()
        speed_row.addWidget(QLabel("Rotation speed"))
        self.speed_value = QLabel()
        speed_row.addStretch(1)
        speed_row.addWidget(self.speed_value)
        motion_layout.addLayout(speed_row)

        self.speed_slider = QSlider(Qt.Orientation.Horizontal)
        self.speed_slider.setRange(1, 10)
        self.speed_slider.setValue(
            settings.value("rotation_speed_level", 2, type=int)
        )
        self.speed_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.speed_slider.setTickInterval(1)
        self.speed_slider.valueChanged.connect(self.update_speed_label)
        motion_layout.addWidget(self.speed_slider)
        self.update_speed_label(self.speed_slider.value())
        root.addWidget(motion)

        startup = QGroupBox("Startup")
        startup_layout = QVBoxLayout(startup)
        self.autostart_check = QCheckBox("Start Cozy Orbit when I log in")
        self.autostart_check.setChecked(autostart_enabled())
        startup_layout.addWidget(self.autostart_check)
        root.addWidget(startup)

        info = QLabel(
            "Changes are saved on this device and applied immediately. "
            "The widget's right-click menu also contains refresh and quit."
        )
        info.setWordWrap(True)
        root.addWidget(info)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

        self.setStyleSheet("""
            QDialog { background: palette(window); }
            QGroupBox {
                font-weight: 600; border: 1px solid palette(mid);
                border-radius: 8px; margin-top: 10px; padding: 10px;
            }
            QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 4px; }
            QPushButton { padding: 6px 14px; }
        """)

    def preview_theme(self, name: str):
        parent = self.parent()
        if hasattr(parent, "preview_theme"):
            parent.preview_theme(name)

    def reject(self):
        # Undo any live theme preview.
        parent = self.parent()
        if hasattr(parent, "apply_preferences"):
            parent.apply_preferences()
        super().reject()

    def update_speed_label(self, value: int):
        labels = {
            1: "Very slow", 2: "Slow", 3: "Gentle", 4: "Relaxed",
            5: "Normal", 6: "Lively", 7: "Fast", 8: "Very fast",
            9: "Rapid", 10: "Maximum",
        }
        self.speed_value.setText(labels.get(value, "Slow"))

    def save_preferences(self) -> bool:
        """Persist settings. Returns False if the autostart entry failed."""
        self.settings.setValue("theme", self.theme_combo.currentText())
        self.settings.setValue("rotation_enabled", self.rotate_check.isChecked())
        self.settings.setValue("rotation_speed_level", self.speed_slider.value())
        self.settings.sync()
        wanted = self.autostart_check.isChecked()
        if wanted != autostart_enabled():
            return set_autostart(wanted)
        return True


# ---------------------------------------------------------------------------
# Main widget
# ---------------------------------------------------------------------------

class CozyOrbit(QWidget):
    # Emitted from worker threads; delivered on the GUI thread.
    status_ready = Signal(dict)
    job_finished = Signal(object)

    def __init__(self):
        super().__init__()
        self.settings = QSettings(ORG_NAME, SETTINGS_DOMAIN)
        self.setWindowTitle(APP_NAME)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_QuitOnClose, False)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setFixedSize(SIZE, SIZE)
        self.setMouseTracking(True)
        # Resolve icons from the desktop's active icon theme (normally KDE Breeze).
        self.system_icons = [desktop_icon(names) for names in SYSTEM_ICON_CANDIDATES]

        self.theme_name = self.settings.value("theme", "Pastel Pink", type=str)
        if self.theme_name not in THEMES:
            self.theme_name = "Pastel Pink"
        self.tinted_icons = self.make_tinted_icons()
        self.rotation_enabled = self.settings.value(
            "rotation_enabled", True, type=bool
        )
        self.rotation_speed_level = self.settings.value(
            "rotation_speed_level", 2, type=int
        )
        self.rotation_speed = self.speed_from_level(self.rotation_speed_level)

        self._progress = 0.0
        self.rotation = 0.0
        saved_offsets = self.settings.value("control_offsets", [])
        try:
            self.control_offsets = [
                float(saved_offsets[i]) if i < len(saved_offsets) else 0.0
                for i in range(8)
            ]
        except (TypeError, ValueError, IndexError):
            self.control_offsets = [0.0] * 8
        self.hovered_index = -1
        self.dragging_control = False
        self.expanded = False
        self.rotation_paused = False
        self.pressed_index = -1
        self.press_position = QPointF()
        self.press_global_position = None
        self.press_window_position = None
        self.dragging = False
        self.move_started = False
        self._last_frame = time.monotonic()
        self._status_busy = False

        self.rotation_resume_timer = QTimer(self)
        self.rotation_resume_timer.setSingleShot(True)
        self.rotation_resume_timer.timeout.connect(self.resume_rotation)

        self.position_timer = QTimer(self)
        self.position_timer.setSingleShot(True)
        self.position_timer.setInterval(600)
        self.position_timer.timeout.connect(self.save_position)
        self.restore_position()

        self.wifi = "Unknown"
        self.bluetooth = "Unknown"
        self.battery = "N/A"
        self.battery_state = ""
        self.message = ""

        self.status_ready.connect(self.apply_status)
        self.job_finished.connect(self.on_job_finished)

        self.animation = QPropertyAnimation(self, b"progress", self)
        self.animation.setDuration(350)
        self.animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.animation.finished.connect(self.update_frame_timer)

        self._flower_openness = 0.18
        self.flower_animation = QPropertyAnimation(self, b"flowerOpenness", self)
        self.flower_animation.setDuration(420)
        self.flower_animation.setEasingCurve(QEasingCurve.Type.OutBack)

        # The frame timer only runs while the orbit is open and rotating.
        self.frame_timer = QTimer(self)
        self.frame_timer.setInterval(FRAME_INTERVAL_MS)
        self.frame_timer.setTimerType(Qt.TimerType.PreciseTimer)
        self.frame_timer.timeout.connect(self.animation_frame)

        # Status polling only happens while the orbit is open (see poll_status).
        self.status_timer = QTimer(self)
        self.status_timer.timeout.connect(self.poll_status)
        self.status_timer.start(STATUS_INTERVAL_MS)

        self.notification_timer = QTimer(self)
        self.notification_timer.setSingleShot(True)
        self.notification_timer.timeout.connect(self.clear_message)

        self.refresh_status()

    # ----- configuration ---------------------------------------------------

    @staticmethod
    def speed_from_level(level: int) -> float:
        """Radians per second. Level 2 is gentle: ~2 minutes per revolution."""
        return ROTATION_RAD_PER_SEC_PER_LEVEL * max(1, min(10, level))

    def make_tinted_icons(self):
        """Tint desktop-theme icons to the theme's text colour, HiDPI-aware."""
        tint = QColor(THEMES[self.theme_name]["text"])
        dpr = max(1.0, self.devicePixelRatioF())
        px = int(ICON_SIZE * dpr)
        pixmaps = []
        for icon in self.system_icons:
            if icon.isNull():
                pixmaps.append(QPixmap())
                continue
            source = icon.pixmap(px, px)
            source.setDevicePixelRatio(dpr)
            tinted = QPixmap(source.size())
            tinted.setDevicePixelRatio(dpr)
            tinted.fill(Qt.GlobalColor.transparent)
            painter = QPainter(tinted)
            painter.drawPixmap(0, 0, source)
            painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
            painter.fillRect(QRectF(0, 0, ICON_SIZE, ICON_SIZE), tint)
            painter.end()
            pixmaps.append(tinted)
        return pixmaps

    @property
    def theme(self):
        # Not called "palette": that would shadow QWidget.palette().
        return THEMES[self.theme_name]

    def preview_theme(self, name: str):
        if name in THEMES:
            self.theme_name = name
            self.tinted_icons = self.make_tinted_icons()
            self.update()

    def apply_preferences(self):
        self.theme_name = self.settings.value("theme", "Pastel Pink", type=str)
        if self.theme_name not in THEMES:
            self.theme_name = "Pastel Pink"
        self.rotation_enabled = self.settings.value(
            "rotation_enabled", True, type=bool
        )
        self.rotation_speed_level = self.settings.value(
            "rotation_speed_level", 2, type=int
        )
        self.rotation_speed = self.speed_from_level(self.rotation_speed_level)
        self.tinted_icons = self.make_tinted_icons()
        self.update_frame_timer()
        self.update()

    # ----- window position -------------------------------------------------

    def restore_position(self):
        # Wayland compositors decide window placement; only restore on X11.
        if is_wayland():
            return
        saved = self.settings.value("position")
        if isinstance(saved, QPoint):
            if QGuiApplication.screenAt(saved + QPoint(SIZE // 2, SIZE // 2)):
                self.move(saved)

    def save_position(self):
        if not is_wayland():
            self.settings.setValue("position", self.pos())

    def moveEvent(self, event):
        super().moveEvent(event)
        self.position_timer.start()

    # ----- animated properties --------------------------------------------

    def get_progress(self):
        return self._progress

    def set_progress(self, value):
        self._progress = max(0.0, min(1.0, float(value)))
        self.update()

    progress = Property(float, get_progress, set_progress)

    def get_flower_openness(self):
        return self._flower_openness

    def set_flower_openness(self, value):
        self._flower_openness = max(0.0, min(1.0, float(value)))
        self.update()

    flowerOpenness = Property(float, get_flower_openness, set_flower_openness)

    def expand(self, state: bool):
        if self.expanded == state:
            return
        self.expanded = state
        self.animation.stop()
        self.animation.setStartValue(self._progress)
        self.animation.setEndValue(1.0 if state else 0.0)
        self.animation.start()
        self.flower_animation.stop()
        self.flower_animation.setStartValue(self._flower_openness)
        self.flower_animation.setEndValue(1.0 if state else 0.18)
        self.flower_animation.start()
        self.update_frame_timer()
        if state:
            self.refresh_status()

    def toggle_expanded(self):
        self.expand(not self.expanded)

    def update_frame_timer(self):
        """Run the frame timer only while there is something to animate."""
        should_run = self.rotation_enabled and (
            self.expanded or self._progress > 0.001
        )
        if should_run and not self.frame_timer.isActive():
            self._last_frame = time.monotonic()
            self.frame_timer.start()
        elif not should_run and self.frame_timer.isActive():
            self.frame_timer.stop()

    def animation_frame(self):
        now = time.monotonic()
        dt = min(now - self._last_frame, 0.1)  # clamp after stalls/suspend
        self._last_frame = now
        if self.rotation_enabled and not self.rotation_paused and self._progress > 0.001:
            self.rotation = (self.rotation + self.rotation_speed * dt) % (2 * math.pi)
            self.update()

    def get_positions(self):
        points = []
        for i in range(8):
            angle = (
                -math.pi / 2 + i * (math.pi / 4)
                + self.rotation + self.control_offsets[i]
            )
            radius = ORBIT_RADIUS * self._progress
            points.append(QPointF(
                CENTER.x() + math.cos(angle) * radius,
                CENTER.y() + math.sin(angle) * radius,
            ))
        return points

    def get_handle_positions(self):
        """Small drag handles sit just outside each control's hover arc."""
        handles = []
        for point in self.get_positions():
            dx, dy = point.x() - CENTER.x(), point.y() - CENTER.y()
            length = max(1.0, math.hypot(dx, dy))
            offset = BUTTON_RADIUS + 11
            handles.append(QPointF(
                point.x() + dx / length * offset,
                point.y() + dy / length * offset,
            ))
        return handles

    @staticmethod
    def distance(a: QPointF, b: QPointF) -> float:
        return math.hypot(a.x() - b.x(), a.y() - b.y())

    # ----- painting --------------------------------------------------------

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        self.draw_background(painter)
        if self._progress > 0.001:
            self.draw_flower(painter)
            self.draw_controls(painter)
        self.draw_center(painter)
        self.draw_notification(painter)
        painter.end()

    def draw_background(self, painter):
        if self._progress <= 0:
            return
        p = self.theme
        radius = 174 * self._progress
        gradient = QLinearGradient(30, 30, SIZE - 30, SIZE - 30)
        c1, c2 = QColor(p["background_start"]), QColor(p["background_end"])
        c1.setAlpha(int(145 * self._progress))
        c2.setAlpha(int(105 * self._progress))
        gradient.setColorAt(0.0, c1)
        gradient.setColorAt(1.0, c2)
        outline = QColor(p["outline"])
        outline.setAlpha(int(175 * self._progress))
        painter.setPen(QPen(outline, 1.4))
        painter.setBrush(QBrush(gradient))
        painter.drawEllipse(CENTER, radius, radius)

    def draw_flower(self, painter):
        p = self.theme
        for i in range(8):
            angle = -90 + i * 45 + math.degrees(self.rotation)
            painter.save()
            painter.translate(CENTER)
            painter.rotate(angle)
            painter.scale(self._progress, self._progress)
            outline = QColor(p["outline"])
            outline.setAlpha(180)
            painter.setPen(QPen(outline, 1.2))
            painter.setBrush(QColor(p["petal_a"] if i % 2 == 0 else p["petal_b"]))
            painter.drawEllipse(QRectF(-15, -94, 30, 63))
            painter.restore()

    def button_is_dim(self, index: int) -> bool:
        """Wi-Fi / Bluetooth buttons fade when the radio is off or unavailable."""
        if index == 0:
            return self.wifi in ("Off", "N/A")
        if index == 1:
            return self.bluetooth in ("Off", "N/A")
        return False

    def draw_controls(self, painter):
        p = self.theme
        alpha = int(min(255, self._progress * 255))
        for i, pos in enumerate(self.get_positions()):
            painter.save()
            if self.button_is_dim(i):
                painter.setOpacity(0.5)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(30, 25, 45, int(35 * self._progress)))
            painter.drawEllipse(QPointF(pos.x() + 2, pos.y() + 3),
                                BUTTON_RADIUS + 1, BUTTON_RADIUS + 1)

            outline = QColor(p["outline"])
            outline.setAlpha(alpha)
            painter.setPen(QPen(outline, 1.6))
            painter.setBrush(QColor(p["button_a"] if i % 2 == 0 else p["button_b"]))
            painter.drawEllipse(pos, BUTTON_RADIUS, BUTTON_RADIUS)

            icon = self.tinted_icons[i]
            icon_rect = QRectF(pos.x() - ICON_SIZE / 2, pos.y() - ICON_SIZE / 2,
                               ICON_SIZE, ICON_SIZE)
            if not icon.isNull():
                # Keep the target rectangle fractional. Converting it to QRect
                # rounds the position every frame and makes rotating icons jitter.
                painter.drawPixmap(icon_rect, icon, QRectF(icon.rect()))
            else:
                painter.setPen(QColor(p["text"]))
                painter.setFont(QFont("DejaVu Sans", 14, QFont.Weight.Bold))
                painter.drawText(
                    QRectF(pos.x() - 17, pos.y() - 17, 34, 34),
                    Qt.AlignmentFlag.AlignCenter, ICON_FALLBACKS[i],
                )

            if self._progress > 0.90 and i == self.hovered_index:
                # A light, separate arc with a tiny grab point; the control
                # itself never grows or pops out of the orbit.
                arc_rect = QRectF(
                    pos.x() - BUTTON_RADIUS - 8,
                    pos.y() - BUTTON_RADIUS - 8,
                    (BUTTON_RADIUS + 8) * 2,
                    (BUTTON_RADIUS + 8) * 2,
                )
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.setPen(QPen(QColor(p["accent"]), 2.4,
                                    Qt.PenStyle.SolidLine,
                                    Qt.PenCapStyle.RoundCap))
                painter.drawArc(arc_rect, 25 * 16, 290 * 16)
                handle = self.get_handle_positions()[i]
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(QColor(p["accent"]))
                painter.drawEllipse(handle, 4.2, 4.2)
                painter.setPen(QPen(QColor(p["outline"]), 1.0))
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawEllipse(handle, 4.2, 4.2)

            if self._progress > 0.90:
                painter.setFont(QFont("DejaVu Sans", 7, QFont.Weight.DemiBold))
                painter.setPen(QColor(p["text"]))
                painter.drawText(
                    QRectF(pos.x() - 42, pos.y() + 31, 84, 18),
                    Qt.AlignmentFlag.AlignCenter, self.get_label(i),
                )
            painter.restore()

    def get_label(self, index):
        compact = ["Wi-Fi", "Bluetooth", "Vol −", "Vol +", "Battery",
                   "Bright −", "Bright +", "Settings"]
        if index == 0:
            return f"Wi-Fi {self.wifi}"
        if index == 1:
            return f"BT {self.bluetooth}"
        if index == 4:
            return self.battery + (" ⚡" if self.battery_state == "Charging" else "")
        return compact[index]

    def draw_center(self, painter):
        p = self.theme
        painter.save()
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(30, 25, 45, 45))
        painter.drawEllipse(QPointF(CENTER.x() + 2, CENTER.y() + 4),
                            ORB_RADIUS + 3, ORB_RADIUS + 3)

        gradient = QLinearGradient(
            CENTER.x() - ORB_RADIUS, CENTER.y() - ORB_RADIUS,
            CENTER.x() + ORB_RADIUS, CENTER.y() + ORB_RADIUS,
        )
        gradient.setColorAt(0.0, QColor(p["center_start"]))
        gradient.setColorAt(1.0, QColor(p["center_end"]))
        painter.setPen(QPen(QColor(p["outline"]), 2))
        painter.setBrush(QBrush(gradient))
        painter.drawEllipse(CENTER, ORB_RADIUS, ORB_RADIUS)

        # Six petals unfold from the centre whenever the orbit opens.
        petal_colour = QColor(p["center_icon"])
        painter.setPen(QPen(QColor(p["outline"]), 0.8))
        painter.setBrush(petal_colour)
        openness = self._flower_openness
        for i in range(6):
            painter.save()
            painter.translate(CENTER)
            painter.rotate(i * 60 - 90)
            painter.translate(0, -8 - 8 * openness)
            painter.scale(0.55 + 0.45 * openness, 0.55 + 0.45 * openness)
            painter.drawEllipse(QRectF(-5.5, -10, 11, 17))
            painter.restore()
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(p["accent"]))
        painter.drawEllipse(CENTER, 5.5, 5.5)
        painter.restore()

    def draw_notification(self, painter):
        if not self.message:
            return
        p = self.theme
        painter.save()
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(p["menu_bg"]))
        painter.drawRoundedRect(QRectF(92, 375, 236, 27), 12, 12)
        painter.setPen(QColor(p["menu_text"]))
        painter.setFont(QFont("DejaVu Sans", 9))
        painter.drawText(QRectF(97, 375, 226, 27),
                         Qt.AlignmentFlag.AlignCenter, self.message)
        painter.restore()

    def notify(self, message: str):
        self.message = message[:58]
        self.notification_timer.start(2600)
        self.update()

    def clear_message(self):
        self.message = ""
        self.update()

    # ----- mouse / keyboard ------------------------------------------------
    # No hover expansion or hover highlighting.

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape and self.expanded:
            self.expand(False)
            event.accept()
            return
        super().keyPressEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.RightButton:
            pos = QPointF(event.position())
            if self._progress > 0.90:
                for index, point in enumerate(self.get_positions()[:4]):
                    if self.distance(pos, point) <= BUTTON_RADIUS + 12:
                        if index < 2:
                            self.open_device_settings("wifi" if index == 0 else "bluetooth")
                        else:
                            self.toggle_mute()
                        event.accept()
                        return
            self.context_menu(event.globalPosition().toPoint())
            return
        if event.button() != Qt.MouseButton.LeftButton:
            return

        pos = QPointF(event.position())
        self.press_position = pos
        self.press_global_position = event.globalPosition().toPoint()
        self.press_window_position = self.pos()
        self.dragging = False
        self.move_started = False
        self.dragging_control = False
        self.pressed_index = -1

        if self.distance(pos, CENTER) <= ORB_RADIUS + 10:
            event.accept()
            return

        if self._progress > 0.90:
            # The small outer handle is the drag target. Dragging it moves only
            # that control around the orbit, not the whole widget or control set.
            for i, handle in enumerate(self.get_handle_positions()):
                if self.distance(pos, handle) <= 10:
                    self.pressed_index = i
                    self.dragging_control = True
                    self.rotation_paused = True
                    self.rotation_resume_timer.stop()
                    event.accept()
                    return

            for i, point in enumerate(self.get_positions()):
                if self.distance(pos, point) <= BUTTON_RADIUS + 12:
                    self.pressed_index = i
                    self.rotation_paused = True
                    self.rotation_resume_timer.stop()
                    event.accept()
                    return

    def _manual_move(self, current: QPoint):
        self.move(current - (self.press_global_position - self.press_window_position))

    def mouseMoveEvent(self, event):
        pos = QPointF(event.position())

        if self.press_global_position is None:
            new_hover = -1
            if self._progress > 0.90:
                for i, point in enumerate(self.get_positions()):
                    if self.distance(pos, point) <= BUTTON_RADIUS + 12:
                        new_hover = i
                        break
                    if self.distance(pos, self.get_handle_positions()[i]) <= 10:
                        new_hover = i
                        break
            if new_hover != self.hovered_index:
                self.hovered_index = new_hover
                self.update()
            return

        if self.dragging_control and self.pressed_index >= 0:
            dx = pos.x() - CENTER.x()
            dy = pos.y() - CENTER.y()
            angle = math.atan2(dy, dx)
            base = -math.pi / 2 + self.pressed_index * (math.pi / 4)
            offset = angle - base - self.rotation
            self.control_offsets[self.pressed_index] = (
                offset + math.pi
            ) % (2 * math.pi) - math.pi
            self.update()
            event.accept()
            return

        if self.distance(self.press_position, CENTER) > ORB_RADIUS + 10:
            event.accept()
            return
        current = event.globalPosition().toPoint()
        dx = current.x() - self.press_global_position.x()
        dy = current.y() - self.press_global_position.y()
        if not self.dragging and math.hypot(dx, dy) >= DRAG_THRESHOLD:
            self.dragging = True
            handle = self.windowHandle()
            if handle is not None:
                self.move_started = bool(handle.startSystemMove())
        if self.dragging and not self.move_started and not is_wayland():
            self._manual_move(current)
        event.accept()

    def mouseReleaseEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton:
            return

        if self.dragging_control:
            self.settings.setValue("control_offsets", self.control_offsets)
            self.dragging_control = False
            self.pressed_index = -1
            self.rotation_paused = False
            self.rotation_resume_timer.start(500)
            self.press_global_position = None
            self.press_window_position = None
            self.update()
            event.accept()
            return

        if self.press_global_position is not None:
            if self.distance(self.press_position, CENTER) <= ORB_RADIUS + 10:
                was_drag = self.dragging
                self.press_global_position = None
                self.press_window_position = None
                self.rotation_paused = False
                self.dragging = False
                if not was_drag:
                    self.toggle_expanded()
                self.update()
                event.accept()
                return

        if self.pressed_index >= 0:
            index = self.pressed_index
            self.pressed_index = -1
            if self._progress > 0.90 and self.distance(
                QPointF(event.position()), self.get_positions()[index]
            ) <= BUTTON_RADIUS + 14:
                self.activate(index)
                self.rotation_resume_timer.start(900)
            else:
                self.rotation_paused = False
            self.update()
        self.press_global_position = None
        self.press_window_position = None
        event.accept()

    def leaveEvent(self, event):
        if self.press_global_position is None and self.hovered_index != -1:
            self.hovered_index = -1
            self.update()
        super().leaveEvent(event)

    def mouseDoubleClickEvent(self, event):
        # Treat a double-click as two deliberate centre clicks, without a special action.
        event.accept()

    def resume_rotation(self):
        self.rotation_paused = False
        self.update()

    # ----- system status (background threads) ------------------------------

    def poll_status(self):
        # Nothing on screen needs fresh data while the orbit is closed.
        if self.expanded:
            self.refresh_status()

    def refresh_status(self):
        self.refresh_battery()  # a cheap sysfs read, fine on the GUI thread
        if not self._status_busy:
            self._status_busy = True
            threading.Thread(target=self._status_worker, daemon=True).start()
        self.update()

    def _status_worker(self):
        try:
            data = {"wifi": query_wifi(), "bluetooth": query_bluetooth()}
        except Exception:
            data = {}
        self.status_ready.emit(data)

    def apply_status(self, data: dict):
        self._status_busy = False
        self.wifi = data.get("wifi", self.wifi)
        self.bluetooth = data.get("bluetooth", self.bluetooth)
        self.update()

    def refresh_battery(self):
        for battery in Path("/sys/class/power_supply").glob("BAT*"):
            try:
                capacity = (battery / "capacity").read_text().strip()
                state = (battery / "status").read_text().strip()
                if capacity.isdigit():
                    self.battery = capacity + "%"
                    self.battery_state = state
                    return
            except OSError:
                continue
        self.battery = "N/A"
        self.battery_state = ""

    # ----- actions ---------------------------------------------------------

    def run_job(self, job):
        """Run `job() -> JobResult` off the GUI thread."""
        def worker():
            try:
                result = job()
            except Exception as exc:  # never let a worker die silently
                result = JobResult(False, f"Error: {exc}")
            self.job_finished.emit(result)
        threading.Thread(target=worker, daemon=True).start()

    def on_job_finished(self, result: JobResult):
        if result.permission_error:
            self.show_brightness_permission_help()
            return
        self.notify(result.message)
        if result.ok:
            QTimer.singleShot(700, self.refresh_status)

    def execute(self, args, success_message):
        """Run a command in the background; `success_message` may be a callable."""
        def job():
            if not has_command(args[0]):
                return JobResult(False, f"Missing command: {args[0]}")
            result = run_command(args)
            if result is None:
                return JobResult(False, "Command timed out or failed")
            if result.returncode != 0:
                error = result.stderr.strip() or result.stdout.strip()
                permission = args[0] == "brightnessctl" and any(
                    term in error.lower()
                    for term in ("permission denied", "operation not permitted", "access denied")
                )
                message = error.splitlines()[-1] if error else "Operation failed"
                return JobResult(False, message, permission)
            message = success_message() if callable(success_message) else success_message
            return JobResult(True, message)
        self.run_job(job)

    def activate(self, index):
        actions = {
            0: self.toggle_wifi,
            1: self.toggle_bluetooth,
            2: lambda: self.change_volume(-1),
            3: lambda: self.change_volume(+1),
            4: self.show_battery,
            5: lambda: self.change_brightness(-1),
            6: lambda: self.change_brightness(+1),
            7: self.open_widget_settings,
        }
        action = actions.get(index)
        if action:
            action()

    def toggle_wifi(self):
        if self.wifi not in ("On", "Off"):
            self.notify("Wi-Fi status unavailable")
            return
        state = "off" if self.wifi == "On" else "on"
        self.execute(["nmcli", "radio", "wifi", state], f"Wi-Fi {state.upper()}")

    def toggle_bluetooth(self):
        if self.bluetooth not in ("On", "Off"):
            self.notify("Bluetooth unavailable")
            return
        state = "off" if self.bluetooth == "On" else "on"
        self.execute(["bluetoothctl", "power", state], f"Bluetooth {state.upper()}")

    def change_volume(self, direction: int):
        sign = "+" if direction > 0 else "-"
        if has_command("wpctl"):
            # -l 1.0 stops the volume going past 100%.
            self.execute(
                ["wpctl", "set-volume", "-l", "1.0", "@DEFAULT_AUDIO_SINK@", f"5%{sign}"],
                read_volume,
            )
        elif has_command("pactl"):
            self.execute(
                ["pactl", "set-sink-volume", "@DEFAULT_SINK@", f"{sign}5%"],
                read_volume,
            )
        else:
            self.notify("Audio control unavailable")

    def toggle_mute(self):
        if has_command("wpctl"):
            self.execute(["wpctl", "set-mute", "@DEFAULT_AUDIO_SINK@", "toggle"], read_volume)
        elif has_command("pactl"):
            self.execute(["pactl", "set-sink-mute", "@DEFAULT_SINK@", "toggle"], read_volume)
        else:
            self.notify("Audio control unavailable")

    def change_brightness(self, direction: int):
        if not has_command("brightnessctl"):
            self.notify("Install brightnessctl")
            return
        amount = "5%+" if direction > 0 else "5%-"
        self.execute(["brightnessctl", "set", amount], read_brightness)

    def show_brightness_permission_help(self):
        details = (
            "Cozy Orbit can find the brightness controller, but your user account "
            "does not have permission to change it.\n\n"
            "On Kubuntu, first inspect the device permissions with:\n"
            "  ls -l /sys/class/backlight/*/brightness\n\n"
            "If the device is owned by the video group, you can add your account "
            "to that group with:\n"
            "  sudo usermod -aG video $USER\n\n"
            "Then fully log out and log back in (or reboot). This only helps when "
            "the backlight device grants write access to the video group. Some "
            "hardware needs a device-specific udev rule instead.\n\n"
            "Do not run Cozy Orbit as root."
        )
        QMessageBox.warning(self, "Brightness permission required", details)

    def show_battery(self):
        self.refresh_battery()
        detail = f"Battery: {self.battery}"
        if self.battery_state:
            detail += f" ({self.battery_state})"
        self.notify(detail)

    def open_widget_settings(self):
        dialog = WidgetSettingsDialog(self.settings, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            autostart_ok = dialog.save_preferences()
            self.apply_preferences()
            self.notify("Widget settings saved" if autostart_ok
                        else "Saved, but couldn't update autostart")

    def showEvent(self, event):
        super().showEvent(event)
        # Rebuild icons now that the real screen (and its DPI) is known.
        self.tinted_icons = self.make_tinted_icons()
        self.update_frame_timer()
        # Kick a first paint/status refresh after the compositor has mapped us.
        QTimer.singleShot(0, self.update)
        QTimer.singleShot(150, self.refresh_status)

    def open_device_settings(self, device: str):
        modules = {
            "wifi": ("kcm_networkmanagement", "Wi-Fi"),
            "bluetooth": ("kcm_bluetooth", "Bluetooth"),
        }
        module, label = modules[device]
        if launch_application("kcmshell6", (module,)):
            self.notify(f"Opening {label} settings")
        elif launch_application("systemsettings", (module,)):
            self.notify(f"Opening {label} settings")
        else:
            self.notify(f"{label} settings unavailable")

    def open_kde_settings(self):
        if launch_application("systemsettings"):
            self.notify("Opening KDE System Settings")
        else:
            self.notify("KDE System Settings not found")

    def context_menu(self, point):
        p = self.theme
        menu = QMenu(self)
        menu.setStyleSheet(f"""
            QMenu {{
                background: {p['menu_bg']}; color: {p['menu_text']};
                border: 1px solid {p['accent']}; border-radius: 10px;
                padding: 6px;
            }}
            QMenu::item {{ padding: 8px 22px; border-radius: 5px; }}
            QMenu::item:selected {{ background: {p['menu_selected']}; }}
            QMenu::separator {{ height: 1px; background: {p['accent']}; margin: 5px 8px; }}
        """)
        settings_action = QAction("Cozy Orbit Widget Settings…", menu)
        settings_action.triggered.connect(self.open_widget_settings)
        menu.addAction(settings_action)

        wifi_settings_action = QAction("Wi-Fi Settings…", menu)
        wifi_settings_action.triggered.connect(lambda: self.open_device_settings("wifi"))
        menu.addAction(wifi_settings_action)

        bluetooth_settings_action = QAction("Bluetooth Settings…", menu)
        bluetooth_settings_action.triggered.connect(lambda: self.open_device_settings("bluetooth"))
        menu.addAction(bluetooth_settings_action)

        mute_action = QAction("Mute / unmute", menu)
        mute_action.triggered.connect(self.toggle_mute)
        menu.addAction(mute_action)

        refresh_action = QAction("Refresh device status", menu)
        refresh_action.triggered.connect(self.refresh_status)
        menu.addAction(refresh_action)

        menu.addSeparator()
        kde_action = QAction("KDE System Settings", menu)
        kde_action.triggered.connect(self.open_kde_settings)
        menu.addAction(kde_action)

        menu.addSeparator()
        quit_action = QAction("Quit Cozy Orbit", menu)
        quit_action.triggered.connect(QApplication.quit)
        menu.addAction(quit_action)
        menu.exec(point)

    def closeEvent(self, event):
        self.save_position()
        self.frame_timer.stop()
        self.status_timer.stop()
        self.notification_timer.stop()
        self.animation.stop()
        event.accept()


def main():
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(APP_VERSION)
    app.setOrganizationName(ORG_NAME)
    app.setOrganizationDomain(SETTINGS_DOMAIN)
    # The floating widget is a Qt.Tool window; closing a preferences dialog
    # must never make QApplication quit. Quit remains available in the menu.
    app.setQuitOnLastWindowClosed(False)

    # Allow only one running copy per user.
    lock = QLockFile(str(Path(tempfile.gettempdir()) / f"cozy-orbit-{os.getuid()}.lock"))
    lock.setStaleLockTime(0)  # a lock left by a crashed process is ignored
    if not lock.tryLock(100):
        print(f"{APP_NAME} is already running.", file=sys.stderr)
        return 0

    widget = CozyOrbit()
    widget.show()
    code = app.exec()
    lock.unlock()
    return code


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        print(f"{APP_NAME} error: {exc}", file=sys.stderr)
        raise