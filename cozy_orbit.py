#!/usr/bin/env python3
"""
Cozy Orbit v0.8.0
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
"""

from __future__ import annotations

import math
import os
import shutil
import subprocess
import sys
from pathlib import Path

from PySide6.QtCore import (
    Qt, QPointF, QRectF, QTimer, QEasingCurve,
    QPropertyAnimation, Property, QSettings,
)
from PySide6.QtGui import (
    QAction, QColor, QFont, QPainter, QPen, QBrush, QLinearGradient, QIcon, QPixmap,
)
from PySide6.QtWidgets import (
    QApplication, QWidget, QMenu, QDialog, QVBoxLayout, QHBoxLayout,
    QLabel, QComboBox, QSlider, QCheckBox, QDialogButtonBox,
    QFormLayout, QGroupBox, QPushButton, QMessageBox,
)

APP_NAME = "Cozy Orbit"
APP_VERSION = "0.8.0"
ORG_NAME = "CozyOrbit"
SETTINGS_DOMAIN = "cozy-orbit"

SIZE = 420
CENTER = QPointF(SIZE / 2, SIZE / 2)
ORB_RADIUS = 34
BUTTON_RADIUS = 26
ORBIT_RADIUS = 137
FRAME_INTERVAL_MS = 16
STATUS_INTERVAL_MS = 3000
DRAG_THRESHOLD = 8

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


def desktop_icon(candidates: tuple[str, ...]) -> QIcon:
    """Return the first icon available in the user's current desktop theme."""
    for name in candidates:
        icon = QIcon.fromTheme(name)
        if not icon.isNull():
            return icon
    return QIcon()

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

    def update_speed_label(self, value: int):
        labels = {
            1: "Very slow", 2: "Slow", 3: "Gentle", 4: "Relaxed",
            5: "Normal", 6: "Lively", 7: "Fast", 8: "Very fast",
            9: "Rapid", 10: "Maximum",
        }
        self.speed_value.setText(labels.get(value, "Slow"))

    def save_preferences(self):
        self.settings.setValue("theme", self.theme_combo.currentText())
        self.settings.setValue("rotation_enabled", self.rotate_check.isChecked())
        self.settings.setValue("rotation_speed_level", self.speed_slider.value())
        self.settings.sync()


class CozyOrbit(QWidget):
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
        self.setFixedSize(SIZE, SIZE)
        self.setMouseTracking(False)
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
        self.expanded = False
        self.rotation_paused = False
        self.pressed_index = -1
        self.press_position = QPointF()
        self.press_global_position = None
        self.press_window_position = None
        self.dragging = False
        self.move_started = False
        self.rotation_resume_timer = QTimer(self)
        self.rotation_resume_timer.setSingleShot(True)
        self.rotation_resume_timer.timeout.connect(self.resume_rotation)

        self.wifi = "Unknown"
        self.bluetooth = "Unknown"
        self.battery = "N/A"
        self.battery_state = ""
        self.message = ""

        self.animation = QPropertyAnimation(self, b"progress", self)
        self.animation.setDuration(350)
        self.animation.setEasingCurve(QEasingCurve.Type.OutCubic)

        self._flower_openness = 0.18
        self.flower_animation = QPropertyAnimation(self, b"flowerOpenness", self)
        self.flower_animation.setDuration(420)
        self.flower_animation.setEasingCurve(QEasingCurve.Type.OutBack)

        self.frame_timer = QTimer(self)
        self.frame_timer.setInterval(FRAME_INTERVAL_MS)
        self.frame_timer.setTimerType(Qt.TimerType.PreciseTimer)
        self.frame_timer.timeout.connect(self.animation_frame)
        # Start after the window is shown; this avoids an occasional missed
        # first animation frame during Wayland window initialisation.

        self.status_timer = QTimer(self)
        self.status_timer.timeout.connect(self.refresh_status)
        self.status_timer.start(STATUS_INTERVAL_MS)

        self.notification_timer = QTimer(self)
        self.notification_timer.setSingleShot(True)
        self.notification_timer.timeout.connect(self.clear_message)

        self.refresh_status()

    @staticmethod
    def speed_from_level(level: int) -> float:
        # Level 2 is intentionally gentle: one full revolution takes about 2 minutes.
        return 0.0009 * max(1, min(10, level)) / 2

    def make_tinted_icons(self):
        """Tint desktop-theme icons to match the current theme's readable text colour."""
        tint = QColor(THEMES[self.theme_name]["text"])
        pixmaps = []
        for icon in self.system_icons:
            if icon.isNull():
                pixmaps.append(QPixmap())
                continue
            source = icon.pixmap(32, 32)
            tinted = QPixmap(source.size())
            tinted.fill(Qt.GlobalColor.transparent)
            painter = QPainter(tinted)
            painter.drawPixmap(0, 0, source)
            painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
            painter.fillRect(tinted.rect(), tint)
            painter.end()
            pixmaps.append(tinted)
        return pixmaps

    @property
    def palette(self):
        return THEMES[self.theme_name]

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

    def toggle_expanded(self):
        self.expand(not self.expanded)

    def animation_frame(self):
        if self.expanded and self.rotation_enabled and not self.rotation_paused:
            self.rotation = (self.rotation + self.rotation_speed) % (2 * math.pi)
            self.update()

    def get_positions(self):
        points = []
        for i in range(8):
            angle = -math.pi / 2 + i * (math.pi / 4) + self.rotation
            radius = ORBIT_RADIUS * self._progress
            points.append(QPointF(
                CENTER.x() + math.cos(angle) * radius,
                CENTER.y() + math.sin(angle) * radius,
            ))
        return points

    @staticmethod
    def distance(a: QPointF, b: QPointF) -> float:
        return math.hypot(a.x() - b.x(), a.y() - b.y())

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)
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
        p = self.palette
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
        p = self.palette
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

    def draw_controls(self, painter):
        p = self.palette
        alpha = int(min(255, self._progress * 255))
        for i, pos in enumerate(self.get_positions()):
            painter.save()
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
            icon_rect = QRectF(pos.x() - 14, pos.y() - 14, 28, 28)
            if not icon.isNull():
                painter.drawPixmap(icon_rect.toRect(), icon)
            else:
                painter.setPen(QColor(p["text"]))
                painter.setFont(QFont("DejaVu Sans", 14, QFont.Weight.Bold))
                painter.drawText(
                    QRectF(pos.x() - 17, pos.y() - 17, 34, 34),
                    Qt.AlignmentFlag.AlignCenter, ICON_FALLBACKS[i],
                )

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
            return self.battery
        return compact[index]

    def draw_center(self, painter):
        p = self.palette
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
        p = self.palette
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

    # Mouse interaction: no hover expansion or hover highlighting.
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.RightButton:
            pos = QPointF(event.position())
            if self._progress > 0.90:
                for index, point in enumerate(self.get_positions()[:2]):
                    if self.distance(pos, point) <= BUTTON_RADIUS + 12:
                        self.open_device_settings("wifi" if index == 0 else "bluetooth")
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
        self.pressed_index = -1

        if self.distance(pos, CENTER) <= ORB_RADIUS + 10:
            # Keep the orbit moving while the centre is pressed or dragged.
            # Do not start a compositor move on every centre click. Starting a
            # move immediately can swallow the click/release on Wayland.
            event.accept()
            return

        if self._progress > 0.90:
            for i, point in enumerate(self.get_positions()):
                if self.distance(pos, point) <= BUTTON_RADIUS + 12:
                    self.pressed_index = i
                    self.rotation_paused = True
                    self.rotation_resume_timer.stop()
                    event.accept()
                    return

    def mouseMoveEvent(self, event):
        if self.press_global_position is None:
            return
        current = event.globalPosition().toPoint()
        dx = current.x() - self.press_global_position.x()
        dy = current.y() - self.press_global_position.y()
        if (not self.dragging and math.hypot(dx, dy) >= DRAG_THRESHOLD
                and self.distance(self.press_position, CENTER) <= ORB_RADIUS + 10):
            self.dragging = True
            # Begin a native move only after the pointer has actually moved.
            # This keeps an ordinary click reliable while preserving Wayland drag.
            handle = self.windowHandle()
            if handle is not None:
                self.move_started = bool(handle.startSystemMove())
            if not self.move_started and os.environ.get("XDG_SESSION_TYPE") != "wayland":
                self.move(current - (self.press_global_position - self.press_window_position))
        elif self.dragging and not self.move_started and os.environ.get("XDG_SESSION_TYPE") != "wayland":
            self.move(current - (self.press_global_position - self.press_window_position))
        event.accept()

    def mouseReleaseEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton:
            return

        if self.press_global_position is not None:
            if self.distance(self.press_position, CENTER) <= ORB_RADIUS + 10:
                was_drag = self.dragging
                self.press_global_position = None
                self.press_window_position = None
                self.rotation_paused = False
                self.dragging = False
                if not self.frame_timer.isActive():
                    self.frame_timer.start()
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
                # Hold the orbit still briefly so the selected control is easy
                # to follow while Wi-Fi/Bluetooth or another action responds.
                self.rotation_resume_timer.start(900)
            else:
                self.rotation_paused = False
            self.update()
        self.press_global_position = None
        self.press_window_position = None
        event.accept()

    def mouseDoubleClickEvent(self, event):
        # Treat a double-click as two deliberate centre clicks, without a special action.
        event.accept()

    def resume_rotation(self):
        self.rotation_paused = False
        self.update()

    # System status
    def refresh_status(self):
        self.refresh_wifi()
        self.refresh_bluetooth()
        self.refresh_battery()
        self.update()

    def refresh_wifi(self):
        if not has_command("nmcli"):
            self.wifi = "N/A"
            return
        state = get_output(["nmcli", "radio", "wifi"], "unknown").lower()
        self.wifi = "On" if state == "enabled" else (
            "Off" if state == "disabled" else "Unknown"
        )

    def refresh_bluetooth(self):
        if not has_command("bluetoothctl"):
            self.bluetooth = "N/A"
            return
        result = run_command(["bluetoothctl", "show"])
        if result is None:
            self.bluetooth = "Unknown"
            return
        output = result.stdout.lower()
        if "powered: yes" in output:
            self.bluetooth = "On"
        elif "powered: no" in output:
            self.bluetooth = "Off"
        elif "no default controller" in output:
            self.bluetooth = "N/A"
        else:
            self.bluetooth = "Unknown"

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

    def execute(self, args, success_message):
        if not has_command(args[0]):
            self.notify(f"Missing command: {args[0]}")
            return False
        result = run_command(args)
        if result is None:
            self.notify("Command execution failed")
            return False
        if result.returncode != 0:
            error = result.stderr.strip() or result.stdout.strip()
            if args[0] == "brightnessctl" and any(
                term in error.lower() for term in ("permission denied", "operation not permitted", "access denied")
            ):
                self.show_brightness_permission_help()
            else:
                self.notify(error.splitlines()[-1][:58] if error else "Operation failed")
            return False
        self.notify(success_message)
        QTimer.singleShot(700, self.refresh_status)
        return True

    def activate(self, index):
        actions = {
            0: self.toggle_wifi,
            1: self.toggle_bluetooth,
            2: lambda: self.change_volume("-5%"),
            3: lambda: self.change_volume("+5%"),
            4: self.show_battery,
            5: lambda: self.change_brightness("5%-"),
            6: lambda: self.change_brightness("5%+"),
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

    def change_volume(self, amount):
        if has_command("wpctl"):
            value = "5%+" if amount == "+5%" else "5%-"
            self.execute(
                ["wpctl", "set-volume", "@DEFAULT_AUDIO_SINK@", value],
                f"Volume {amount}",
            )
        elif has_command("pactl"):
            self.execute(
                ["pactl", "set-sink-volume", "@DEFAULT_SINK@", amount],
                f"Volume {amount}",
            )
        else:
            self.notify("Audio control unavailable")

    def change_brightness(self, amount):
        if not has_command("brightnessctl"):
            self.notify("Install brightnessctl")
            return
        self.execute(["brightnessctl", "set", amount], f"Brightness {amount}")

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
            dialog.save_preferences()
            self.apply_preferences()
            self.notify("Widget settings saved")

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
        if not self.frame_timer.isActive():
            self.frame_timer.start()
        self.update()

    def showEvent(self, event):
        super().showEvent(event)
        if not self.frame_timer.isActive():
            self.frame_timer.start()
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
        p = self.palette
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

    widget = CozyOrbit()
    widget.show()
    return app.exec()


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        print(f"{APP_NAME} error: {exc}", file=sys.stderr)
        raise
