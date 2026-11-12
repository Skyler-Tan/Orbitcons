
#!/usr/bin/env python3
"""
Cozy Orbit v0.5.0
Pastel radial desktop control for Kubuntu / KDE Plasma 6.

Designed for:
    Kubuntu
    KDE Plasma 6
    Wayland
    PySide6

Interaction:
    Hover centre       -> Expand
    Move pointer       -> Select controls
    Expanded           -> Slowly rotates clockwise
    Click control      -> Activate
    Drag centre        -> Move window through KDE compositor
    Leave window       -> Collapse
    Right-click        -> Context menu
"""

import math
import os
import shutil
import subprocess
import sys
from pathlib import Path

from PySide6.QtCore import (
    Qt,
    QPointF,
    QRectF,
    QTimer,
    QEasingCurve,
    QPropertyAnimation,
    Property,
)

from PySide6.QtGui import (
    QAction,
    QColor,
    QFont,
    QPainter,
    QPen,
    QBrush,
    QLinearGradient,
)

from PySide6.QtWidgets import (
    QApplication,
    QWidget,
    QMenu,
)


# ==================================================
# CONFIGURATION
# ==================================================

APP_NAME = "Cozy Orbit"
VERSION = "0.5.0"

APP_DIR = Path.home() / ".local/share/cozy-orbit"
APP_DIR.mkdir(parents=True, exist_ok=True)

SIZE = 420

CENTER = QPointF(210, 210)

ORB_RADIUS = 34
BUTTON_RADIUS = 26
ORBIT_RADIUS = 137

ROTATION_SPEED = 0.0025
REFRESH_INTERVAL = 3000

# Pastel colour palette

PINK = QColor("#FFD3E3")
PINK_DARK = QColor("#F7B8D0")

LAVENDER = QColor("#DCCBFA")
LAVENDER_DARK = QColor("#C4A9EB")

PURPLE = QColor("#80658F")
TEXT = QColor("#594563")

WHITE = QColor("#FFFFFF")

# Eight radial controls

LABELS = [
    "Wi-Fi",
    "Bluetooth",
    "Volume Down",
    "Volume Up",
    "Battery",
    "Brightness Down",
    "Brightness Up",
    "Settings",
]

# Use ordinary characters to avoid missing
# Unicode icon fonts on Linux.

ICONS = [
    "W",
    "B",
    "-",
    "+",
    "%",
    "-",
    "+",
    "S",
]


# ==================================================
# SYSTEM UTILITIES
# ==================================================

def has_command(name):
    return shutil.which(name) is not None


def run_command(args, timeout=4):

    try:
        return subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )

    except (
        OSError,
        subprocess.TimeoutExpired,
    ):
        return None


def get_output(args, fallback=""):

    result = run_command(args)

    if result and result.returncode == 0:
        return result.stdout.strip()

    return fallback


def launch_application(name):

    executable = shutil.which(name)

    if not executable:
        return False

    try:
        subprocess.Popen(
            [executable],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )

        return True

    except OSError:
        return False


# ==================================================
# MAIN WINDOW
# ==================================================

class CozyOrbit(QWidget):

    def __init__(self):

        super().__init__()

        self.setWindowTitle(APP_NAME)

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )

        self.setAttribute(
            Qt.WidgetAttribute.WA_TranslucentBackground,
            True,
        )

        self.setMouseTracking(True)

        self.setFixedSize(SIZE, SIZE)

        # ------------------------------------------
        # Animation state
        # ------------------------------------------

        self._progress = 0.0

        self.rotation = 0.0

        self.expanded = False

        self.rotation_paused = False

        # ------------------------------------------
        # Mouse state
        # ------------------------------------------

        self.hover_index = -1

        self.pressed_index = -1

        self.dragging = False

        # ------------------------------------------
        # System state
        # ------------------------------------------

        self.wifi = "Unknown"

        self.bluetooth = "Unknown"

        self.battery = "N/A"

        self.battery_state = ""

        self.message = ""

        # ------------------------------------------
        # Expansion animation
        # ------------------------------------------

        self.animation = QPropertyAnimation(
            self,
            b"progress",
            self,
        )

        self.animation.setDuration(450)

        self.animation.setEasingCurve(
            QEasingCurve.Type.OutCubic
        )

        # ------------------------------------------
        # Main animation timer
        # ------------------------------------------

        self.frame_timer = QTimer(self)

        self.frame_timer.setInterval(16)

        self.frame_timer.timeout.connect(
            self.animation_frame
        )

        self.frame_timer.start()

        # ------------------------------------------
        # System refresh timer
        # ------------------------------------------

        self.status_timer = QTimer(self)

        self.status_timer.timeout.connect(
            self.refresh_status
        )

        self.status_timer.start(
            REFRESH_INTERVAL
        )

        # ------------------------------------------
        # Notification timer
        # ------------------------------------------

        self.notification_timer = QTimer(self)

        self.notification_timer.setSingleShot(True)

        self.notification_timer.timeout.connect(
            self.clear_message
        )

        # ------------------------------------------
        # Start
        # ------------------------------------------

        self.refresh_status()

    # ==================================================
    # ANIMATION PROPERTY
    # ==================================================

    def get_progress(self):
        return self._progress

    def set_progress(self, value):

        self._progress = max(
            0.0,
            min(1.0, value),
        )

        self.update()

    progress = Property(
        float,
        get_progress,
        set_progress,
    )

    def expand(self, state):

        if self.expanded == state:
            return

        self.expanded = state

        self.animation.stop()

        self.animation.setStartValue(
            self._progress
        )

        self.animation.setEndValue(
            1.0 if state else 0.0
        )

        self.animation.start()

    def animation_frame(self):

        if self.expanded and not self.rotation_paused:

            self.rotation = (
                self.rotation + ROTATION_SPEED
            ) % (2 * math.pi)

            self.update()

    # ==================================================
    # RADIAL POSITIONS
    # ==================================================

    def get_positions(self):

        positions = []

        for i in range(8):

            angle = (
                -math.pi / 2
                + i * (math.pi / 4)
                + self.rotation
            )

            radius = (
                ORBIT_RADIUS * self._progress
            )

            x = CENTER.x() + math.cos(angle) * radius

            y = CENTER.y() + math.sin(angle) * radius

            positions.append(
                QPointF(x, y)
            )

        return positions

    @staticmethod
    def distance(a, b):

        return math.hypot(
            a.x() - b.x(),
            a.y() - b.y(),
        )

    # ==================================================
    # PAINTING
    # ==================================================

    def paintEvent(self, event):

        painter = QPainter(self)

        painter.setRenderHint(
            QPainter.RenderHint.Antialiasing
        )

        painter.setRenderHint(
            QPainter.RenderHint.TextAntialiasing
        )

        self.draw_background(painter)

        if self._progress > 0.001:

            self.draw_flower(painter)

            self.draw_controls(painter)

        self.draw_center(painter)

        self.draw_notification(painter)

        painter.end()

    # --------------------------------------------------
    # BACKGROUND
    # --------------------------------------------------

    def draw_background(self, painter):

        progress = self._progress

        if progress <= 0:
            return

        radius = 174 * progress

        gradient = QLinearGradient(
            30, 30, SIZE - 30, SIZE - 30
        )

        gradient.setColorAt(
            0.0,
            QColor(255, 241, 249, int(145 * progress)),
        )

        gradient.setColorAt(
            1.0,
            QColor(226, 213, 250, int(105 * progress)),
        )

        painter.setPen(
            QPen(
                QColor(255, 255, 255, int(175 * progress)),
                1.4,
            )
        )

        painter.setBrush(
            QBrush(gradient)
        )

        painter.drawEllipse(
            CENTER,
            radius,
            radius,
        )

    # --------------------------------------------------
    # FLOWER PETALS
    # --------------------------------------------------

    def draw_flower(self, painter):

        progress = self._progress

        # Eight petals surround the centre.

        for i in range(8):

            angle = (
                -90
                + i * 45
                + math.degrees(self.rotation)
            )

            painter.save()

            painter.translate(CENTER)

            painter.rotate(angle)

            # Petals grow with expansion.

            scale = progress

            painter.scale(
                scale,
                scale,
            )

            painter.setPen(
                QPen(
                    QColor(255, 255, 255, 180),
                    1.2,
                )
            )

            painter.setBrush(
                PINK if i % 2 == 0
                else LAVENDER
            )

            painter.drawEllipse(
                QRectF(
                    -15,
                    -94,
                    30,
                    63,
                )
            )

            painter.restore()

    # --------------------------------------------------
    # RADIAL BUTTONS
    # --------------------------------------------------

    def draw_controls(self, painter):

        positions = self.get_positions()

        alpha = int(
            min(255, self._progress * 255)
        )

        for i, pos in enumerate(positions):

            hovered = (
                i == self.hover_index
            )

            painter.save()

            # Button shadow

            painter.setPen(
                Qt.PenStyle.NoPen
            )

            painter.setBrush(
                QColor(90, 65, 110, int(35 * self._progress))
            )

            painter.drawEllipse(
                QPointF(pos.x() + 2, pos.y() + 3),
                BUTTON_RADIUS + 1,
                BUTTON_RADIUS + 1,
            )

            # Button body

            painter.setPen(
                QPen(
                    QColor(255, 255, 255, alpha),
                    1.6,
                )
            )

            if hovered:

                painter.setBrush(
                    WHITE
                )

                radius = BUTTON_RADIUS + 3

            else:

                painter.setBrush(
                    PINK if i % 2 == 0
                    else LAVENDER
                )

                radius = BUTTON_RADIUS

            painter.drawEllipse(
                pos,
                radius,
                radius,
            )

            # Icon

            painter.setPen(
                TEXT
            )

            painter.setFont(
                QFont(
                    "DejaVu Sans",
                    14,
                    QFont.Weight.Bold,
                )
            )

            painter.drawText(
                QRectF(
                    pos.x() - 17,
                    pos.y() - 17,
                    34,
                    34,
                ),
                Qt.AlignmentFlag.AlignCenter,
                ICONS[i],
            )

            # Labels

            if self._progress > 0.90:

                label = self.get_label(i)

                painter.setFont(
                    QFont(
                        "DejaVu Sans",
                        8,
                        QFont.Weight.DemiBold,
                    )
                )

                painter.setPen(
                    QColor(75, 58, 85, alpha)
                )

                painter.drawText(
                    QRectF(
                        pos.x() - 48,
                        pos.y() + 32,
                        96,
                        20,
                    ),
                    Qt.AlignmentFlag.AlignCenter,
                    label,
                )

            painter.restore()

    def get_label(self, index):

        if index == 0:
            return f"Wi-Fi: {self.wifi}"

        if index == 1:
            return f"BT: {self.bluetooth}"

        if index == 4:
            return f"{self.battery} {self.battery_state}"

        return LABELS[index]

    # --------------------------------------------------
    # CENTRE FLOWER
    # --------------------------------------------------

    def draw_center(self, painter):

        painter.save()

        # Shadow

        painter.setPen(
            Qt.PenStyle.NoPen
        )

        painter.setBrush(
            QColor(90, 60, 100, 45)
        )

        painter.drawEllipse(
            QPointF(
                CENTER.x() + 2,
                CENTER.y() + 4,
            ),
            ORB_RADIUS + 3,
            ORB_RADIUS + 3,
        )

        # Centre body

        painter.setPen(
            QPen(
                WHITE,
                2,
            )
        )

        gradient = QLinearGradient(
            CENTER.x() - ORB_RADIUS,
            CENTER.y() - ORB_RADIUS,
            CENTER.x() + ORB_RADIUS,
            CENTER.y() + ORB_RADIUS,
        )

        gradient.setColorAt(
            0.0,
            QColor("#FFE5EE"),
        )

        gradient.setColorAt(
            1.0,
            QColor("#E4D4FA"),
        )

        painter.setBrush(
            QBrush(gradient)
        )

        painter.drawEllipse(
            CENTER,
            ORB_RADIUS,
            ORB_RADIUS,
        )

        # Centre flower icon

        painter.setPen(
            QColor("#916A9E")
        )

        painter.setFont(
            QFont(
                "DejaVu Sans",
                25,
                QFont.Weight.Bold,
            )
        )

        painter.drawText(
            QRectF(
                CENTER.x() - 25,
                CENTER.y() - 26,
                50,
                52,
            ),
            Qt.AlignmentFlag.AlignCenter,
            "*",
        )

        painter.restore()

    # --------------------------------------------------
    # NOTIFICATIONS
    # --------------------------------------------------

    def draw_notification(self, painter):

        if not self.message:
            return

        painter.save()

        painter.setPen(
            Qt.PenStyle.NoPen
        )

        painter.setBrush(
            QColor(255, 255, 255, 220)
        )

        painter.drawRoundedRect(
            QRectF(100, 375, 220, 27),
            12,
            12,
        )

        painter.setPen(
            TEXT
        )

        painter.setFont(
            QFont(
                "DejaVu Sans",
                9,
            )
        )

        painter.drawText(
            QRectF(105, 375, 210, 27),
            Qt.AlignmentFlag.AlignCenter,
            self.message,
        )

        painter.restore()

    def notify(self, message):

        self.message = message[:55]

        self.notification_timer.start(2500)

        self.update()

    def clear_message(self):

        self.message = ""

        self.update()

    # ==================================================
    # MOUSE INTERACTION
    # ==================================================

    def enterEvent(self, event):

        self.expand(True)

        super().enterEvent(event)

    def leaveEvent(self, event):

        self.hover_index = -1

        self.pressed_index = -1

        self.rotation_paused = False

        self.expand(False)

        self.unsetCursor()

        self.update()

        super().leaveEvent(event)

    def mouseMoveEvent(self, event):

        pos = QPointF(event.position())

        if self.dragging:
            return

        # Find hovered button.

        self.hover_index = -1

        if self._progress > 0.90:

            for i, point in enumerate(
                self.get_positions()
            ):

                if self.distance(
                    pos,
                    point,
                ) < BUTTON_RADIUS + 12:

                    self.hover_index = i

                    break

        # Pointer feedback

        if self.hover_index >= 0:

            self.setCursor(
                Qt.CursorShape.PointingHandCursor
            )

        elif self.distance(
            pos,
            CENTER,
        ) < ORB_RADIUS + 10:

            self.setCursor(
                Qt.CursorShape.OpenHandCursor
            )

        else:

            self.unsetCursor()

        self.update()

    def mousePressEvent(self, event):

        if event.button() == Qt.MouseButton.RightButton:

            self.context_menu(
                event.globalPosition().toPoint()
            )

            return

        if event.button() != Qt.MouseButton.LeftButton:
            return

        pos = QPointF(event.position())

        # Check centre first for dragging.

        if self.distance(
            pos,
            CENTER,
        ) < ORB_RADIUS + 10:

            self.rotation_paused = True

            handle = self.windowHandle()

            if handle is not None:

                # Native KDE / Wayland window movement.
                # Must be initiated during mouse press.

                if handle.startSystemMove():

                    self.dragging = True

                    return

            self.notify(
                "Window movement unavailable"
            )

            return

        # Check radial buttons.

        if self._progress > 0.90:

            for i, point in enumerate(
                self.get_positions()
            ):

                if self.distance(
                    pos,
                    point,
                ) < BUTTON_RADIUS + 12:

                    self.pressed_index = i

                    self.rotation_paused = True

                    return

    def mouseReleaseEvent(self, event):

        if event.button() != Qt.MouseButton.LeftButton:
            return

        if self.dragging:

            self.dragging = False

            self.rotation_paused = False

            return

        if self.pressed_index >= 0:

            index = self.pressed_index

            self.pressed_index = -1

            if self._progress > 0.90:

                positions = self.get_positions()

                if self.distance(
                    QPointF(event.position()),
                    positions[index],
                ) < BUTTON_RADIUS + 14:

                    self.activate(index)

            self.rotation_paused = False

            self.update()

    # ==================================================
    # SYSTEM STATUS
    # ==================================================

    def refresh_status(self):

        self.refresh_wifi()

        self.refresh_bluetooth()

        self.refresh_battery()

        self.update()

    def refresh_wifi(self):

        if not has_command("nmcli"):

            self.wifi = "N/A"

            return

        state = get_output(
            [
                "nmcli",
                "radio",
                "wifi",
            ],
            "unknown",
        )

        if state.lower() == "enabled":

            self.wifi = "On"

        elif state.lower() == "disabled":

            self.wifi = "Off"

        else:

            self.wifi = "Unknown"

    def refresh_bluetooth(self):

        if not has_command("bluetoothctl"):

            self.bluetooth = "N/A"

            return

        result = run_command(
            [
                "bluetoothctl",
                "show",
            ]
        )

        if result is None:

            self.bluetooth = "Unknown"

            return

        text = result.stdout.lower()

        if "powered: yes" in text:

            self.bluetooth = "On"

        elif "powered: no" in text:

            self.bluetooth = "Off"

        elif "no default controller" in text:

            self.bluetooth = "N/A"

        else:

            self.bluetooth = "Unknown"

    def refresh_battery(self):

        batteries = list(
            Path(
                "/sys/class/power_supply"
            ).glob("BAT*")
        )

        for battery in batteries:

            try:

                capacity = (
                    battery / "capacity"
                ).read_text().strip()

                state = (
                    battery / "status"
                ).read_text().strip()

                if capacity.isdigit():

                    self.battery = capacity + "%"

                    self.battery_state = state

                    return

            except OSError:

                continue

        self.battery = "N/A"

        self.battery_state = ""

    # ==================================================
    # COMMAND EXECUTION
    # ==================================================

    def execute(self, args, success_message):

        if not has_command(args[0]):

            self.notify(
                f"Missing: {args[0]}"
            )

            return False

        result = run_command(args)

        if result is None:

            self.notify(
                "Command execution failed"
            )

            return False

        if result.returncode != 0:

            error = result.stderr.strip()

            if error:

                self.notify(
                    error.splitlines()[-1][:55]
                )

            else:

                self.notify(
                    "Operation failed"
                )

            return False

        self.notify(success_message)

        QTimer.singleShot(
            700,
            self.refresh_status,
        )

        return True

    # ==================================================
    # CONTROL ACTIONS
    # ==================================================

    def activate(self, index):

        if index == 0:

            self.toggle_wifi()

        elif index == 1:

            self.toggle_bluetooth()

        elif index == 2:

            self.change_volume("-5%")

        elif index == 3:

            self.change_volume("+5%")

        elif index == 4:

            self.notify(
                f"Battery: {self.battery}"
                + (
                    f" ({self.battery_state})"
                    if self.battery_state else ""
                )
            )

        elif index == 5:

            self.change_brightness("5%-")

        elif index == 6:

            self.change_brightness("5%+")

        elif index == 7:

            self.open_settings()

    # --------------------------------------------------
    # WI-FI
    # --------------------------------------------------

    def toggle_wifi(self):

        if self.wifi not in ("On", "Off"):

            self.notify(
                "Wi-Fi status unavailable"
            )

            return

        state = (
            "off" if self.wifi == "On"
            else "on"
        )

        self.execute(
            [
                "nmcli",
                "radio",
                "wifi",
                state,
            ],
            f"Wi-Fi {state.upper()}",
        )

    # --------------------------------------------------
    # BLUETOOTH
    # --------------------------------------------------

    def toggle_bluetooth(self):

        if self.bluetooth not in ("On", "Off"):

            self.notify(
                "Bluetooth unavailable"
            )

            return

        state = (
            "off" if self.bluetooth == "On"
            else "on"
        )

        self.execute(
            [
                "bluetoothctl",
                "power",
                state,
            ],
            f"Bluetooth {state.upper()}",
        )

    # --------------------------------------------------
    # VOLUME
    # --------------------------------------------------

    def change_volume(self, amount):

        if has_command("wpctl"):

            value = (
                "5%+" if amount == "+5%"
                else "5%-"
            )

            self.execute(
                [
                    "wpctl",
                    "set-volume",
                    "@DEFAULT_AUDIO_SINK@",
                    value,
                ],
                f"Volume {amount}",
            )

        elif has_command("pactl"):

            self.execute(
                [
                    "pactl",
                    "set-sink-volume",
                    "@DEFAULT_SINK@",
                    amount,
                ],
                f"Volume {amount}",
            )

        else:

            self.notify(
                "Audio control unavailable"
            )

    # --------------------------------------------------
    # BRIGHTNESS
    # --------------------------------------------------

    def change_brightness(self, amount):

        if not has_command("brightnessctl"):

            self.notify(
                "Install brightnessctl"
            )

            return

        self.execute(
            [
                "brightnessctl",
                "set",
                amount,
            ],
            f"Brightness {amount}",
        )

    # --------------------------------------------------
    # KDE SETTINGS
    # --------------------------------------------------

    def open_settings(self):

        if launch_application("systemsettings"):

            self.notify(
                "Opening KDE Settings"
            )

        else:

            self.notify(
                "KDE Settings not found"
            )

    # ==================================================
    # CONTEXT MENU
    # ==================================================

    def context_menu(self, point):

        menu = QMenu(self)

        menu.setStyleSheet("""
            QMenu {
                background: #FFF5FA;
                color: #594563;
                border: 1px solid #E8D6ED;
                border-radius: 10px;
                padding: 6px;
            }

            QMenu::item {
                padding: 8px 22px;
                border-radius: 5px;
            }

            QMenu::item:selected {
                background: #E8D9F5;
            }

            QMenu::separator {
                height: 1px;
                background: #E8D6ED;
                margin: 5px 8px;
            }
        """)

        refresh = QAction(
            "Refresh status",
            menu,
        )

        refresh.triggered.connect(
            self.refresh_status
        )

        menu.addAction(refresh)

        menu.addSeparator()

        settings = QAction(
            "KDE System Settings",
            menu,
        )

        settings.triggered.connect(
            self.open_settings
        )

        menu.addAction(settings)

        menu.addSeparator()

        quit_action = QAction(
            "Quit Cozy Orbit",
            menu,
        )

        quit_action.triggered.connect(
            QApplication.quit
        )

        menu.addAction(quit_action)

        menu.exec(point)

    # ==================================================
    # CLEANUP
    # ==================================================

    def closeEvent(self, event):

        self.frame_timer.stop()

        self.status_timer.stop()

        self.notification_timer.stop()

        self.animation.stop()

        event.accept()


# ==================================================
# APPLICATION ENTRY
# ==================================================

def main():

    app = QApplication(sys.argv)

    app.setApplicationName(APP_NAME)

    app.setApplicationVersion(VERSION)

    app.setQuitOnLastWindowClosed(True)

    widget = CozyOrbit()

    widget.show()

    return app.exec()


if __name__ == "__main__":

    try:

        sys.exit(main())

    except Exception as exc:

        print(
            f"Cozy Orbit error: {exc}",
            file=sys.stderr,
        )

        raise
