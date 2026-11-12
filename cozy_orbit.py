
#!/usr/bin/env python3
"""
Cozy Orbit v0.4.0
A lightweight, floating radial control panel for Linux.

Features:
- Animated pastel radial menu
- Wi-Fi and Bluetooth controls
- Volume and brightness controls
- Battery monitoring
- Desktop settings launcher
- Draggable, persistent positioning
- Hover effects and context menu
- Parrot OS, Linux Mint, KDE and XFCE support
"""

import math
import os
import shutil
import subprocess
import sys
from pathlib import Path

from PySide6.QtCore import (
    QPointF, QRectF, Qt, QTimer
)
from PySide6.QtGui import (
    QAction, QColor, QFont, QPainter, QPen,
    QRadialGradient
)
from PySide6.QtWidgets import (
    QApplication, QMenu, QWidget, QToolTip
)


# --------------------------------------------------
# CONFIGURATION
# --------------------------------------------------

APP_NAME = "Cozy Orbit"
VERSION = "0.4.0"

APP_DIR = Path.home() / ".local/share/cozy-orbit"
APP_DIR.mkdir(parents=True, exist_ok=True)

POSITION_FILE = APP_DIR / "position"

SIZE = 420
CENTER = QPointF(210, 210)

ORB_RADIUS = 34
ITEM_RADIUS = 27
ORBIT_RADIUS = 126

REFRESH_INTERVAL = 3000

# Pastel theme
COLORS = {
    "background": QColor(255, 242, 249, 225),
    "border": QColor(255, 255, 255, 190),
    "pink": QColor(255, 202, 222),
    "purple": QColor(213, 196, 246),
    "dark": QColor(91, 69, 105),
    "text": QColor(79, 61, 87),
    "hover": QColor(255, 255, 255, 245),
    "orb": QColor(255, 206, 222, 250),
}

LABELS = [
    "Wi-Fi",
    "Bluetooth",
    "Volume −",
    "Volume +",
    "Battery",
    "Brightness −",
    "Brightness +",
    "Settings",
]

ICONS = [
    "W", "B", "-", "+",
    "%", "-", "+", "S"
]


# --------------------------------------------------
# SYSTEM COMMAND HELPERS
# --------------------------------------------------

def run_command(args, timeout=4):
    """Run a system command safely."""

    try:
        return subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False
        )

    except (OSError, subprocess.TimeoutExpired):
        return None


def get_output(args, fallback=""):
    result = run_command(args)

    if result and result.returncode == 0:
        return result.stdout.strip()

    return fallback


def has_command(name):
    return shutil.which(name) is not None


# --------------------------------------------------
# MAIN APPLICATION
# --------------------------------------------------

class CozyOrbit(QWidget):

    def __init__(self):
        super().__init__()

        self.pressed_index = -1

        self.setWindowTitle(APP_NAME)

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )

        self.setAttribute(
            Qt.WidgetAttribute.WA_TranslucentBackground,
            True
        )

        self.setMouseTracking(True)
        self.setFixedSize(SIZE, SIZE)

        # Animation
        self.expanded = False
        self.progress = 0.0

        # Mouse interaction
        self.drag_origin = None
        self.window_origin = None
        self.hover_index = -1

        # System status
        self.wifi = "Unknown"
        self.bluetooth = "Unknown"
        self.battery = "—"

        self.status_message = ""
        self.status_timer = QTimer(self)
        self.status_timer.setSingleShot(True)
        self.status_timer.timeout.connect(
            self.clear_status
        )

        # Status refresh timer
        self.timer = QTimer(self)
        self.timer.timeout.connect(
            self.refresh_status
        )
        self.timer.start(REFRESH_INTERVAL)

        # Animation timer
        self.anim = QTimer(self)
        self.anim.setInterval(16)
        self.anim.timeout.connect(self.animate)

        self.restore_position()
        self.refresh_status()

    # --------------------------------------------------
    # POSITION MANAGEMENT
    # --------------------------------------------------

    def restore_position(self):

        try:
            x, y = map(
                int,
                POSITION_FILE.read_text().split()
            )

            self.move(x, y)

            screen = QApplication.primaryScreen()
            if screen:
                geometry = screen.availableGeometry()
                max_x = max(geometry.left(), geometry.right() - SIZE + 1)
                max_y = max(geometry.top(), geometry.bottom() - SIZE + 1)

                self.move(
                    max(geometry.left(), min(x, max_x)),
                    max(geometry.top(), min(y, max_y))
                )

        except (OSError, ValueError):

            screen = QApplication.primaryScreen()

            if screen:
                geometry = screen.availableGeometry()

                self.move(
                    geometry.right() - SIZE - 35,
                    geometry.bottom() - SIZE - 65
                )

            else:
                self.move(100, 100)

    def save_position(self):

        try:
            POSITION_FILE.write_text(
                f"{self.x()} {self.y()}\n"
            )
        except OSError:
            pass

    # --------------------------------------------------
    # SYSTEM STATUS
    # --------------------------------------------------

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
            ["nmcli", "radio", "wifi"],
            "Unknown"
        )

        self.wifi = (
            "On" if state.lower() == "enabled"
            else "Off" if state.lower() == "disabled"
            else "Unknown"
        )

    def refresh_bluetooth(self):

        if not has_command("bluetoothctl"):
            self.bluetooth = "N/A"
            return

        result = run_command(
            ["bluetoothctl", "show"]
        )

        if not result:
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
            Path("/sys/class/power_supply").glob("BAT*")
        )

        for battery in batteries:

            try:
                capacity = (
                    battery / "capacity"
                ).read_text().strip()

                if capacity.isdigit():
                    self.battery = capacity + "%"
                    return

            except OSError:
                continue

        self.battery = "N/A"

    # --------------------------------------------------
    # USER FEEDBACK
    # --------------------------------------------------

    def notify(self, message):

        self.status_message = message
        self.status_timer.start(2500)
        self.update()

    def clear_status(self):

        self.status_message = ""
        self.update()

    def execute(self, args, success_message):

    if not has_command(args[0]):
        self.notify(f"Missing: {args[0]}")
        return False

    result = run_command(args)

    if result is None:
        self.notify("Command execution failed")
        return False

    if result.returncode != 0:

        error = result.stderr.strip()

        self.notify(
            error.splitlines()[-1][:55]
            if error else "Operation failed"
        )

        return False

    self.notify(success_message)

    QTimer.singleShot(
        700,
        self.refresh_status
    )

    return True

    # --------------------------------------------------
    # ANIMATION
    # --------------------------------------------------

    def set_expanded(self, state):

        if self.expanded == state:
            return

        self.expanded = state
        self.anim.start()

    def animate(self):

        target = 1.0 if self.expanded else 0.0

        difference = target - self.progress

        if abs(difference) < 0.008:
            self.progress = target
            self.anim.stop()

        else:
            self.progress += difference * 0.22

        self.update()

    # --------------------------------------------------
    # RADIAL POSITIONS
    # --------------------------------------------------

    def item_positions(self):

        positions = []

        for i in range(8):

            angle = math.radians(
                -90 + i * 45
            )

            spin = (
                (1.0 - self.progress)
                * math.radians(75)
            )

            radius = ORBIT_RADIUS * self.progress

            x = CENTER.x() + math.cos(
                angle + spin
            ) * radius

            y = CENTER.y() + math.sin(
                angle + spin
            ) * radius

            positions.append(QPointF(x, y))

        return positions

    def distance(self, a, b):

        return math.hypot(
            a.x() - b.x(),
            a.y() - b.y()
        )

    # --------------------------------------------------
    # DRAWING
    # --------------------------------------------------

    def paintEvent(self, event):

        painter = QPainter(self)

        painter.setRenderHint(
            QPainter.RenderHint.Antialiasing
        )

        self.draw_background(painter)

        if self.progress > 0.001:
            self.draw_radial_menu(painter)

        self.draw_center_orb(painter)

        painter.end()

    def draw_background(self, painter):

        if self.progress <= 0:
            return

        radius = 176 * self.progress

        gradient = QRadialGradient(
            CENTER,
            radius
        )

        gradient.setColorAt(
            0.0,
            QColor(255, 246, 252, int(185 * self.progress))
        )

        gradient.setColorAt(
            1.0,
            QColor(226, 207, 244, int(75 * self.progress))
        )

        painter.setPen(
            QPen(
                COLORS["border"],
                1.3
            )
        )

        painter.setBrush(gradient)

        painter.drawEllipse(
            CENTER,
            radius,
            radius
        )

    def draw_radial_menu(self, painter):

        positions = self.item_positions()

        alpha = int(
            255 * min(1.0, self.progress * 1.8)
        )

        # Connecting lines
        painter.setPen(
            QPen(
                QColor(255, 255, 255, int(120 * self.progress)),
                1.2
            )
        )

        for pos in positions:

            painter.drawLine(
                CENTER,
                pos
            )

        # Control buttons
        for i, pos in enumerate(positions):

            hovered = i == self.hover_index

            if hovered:
                painter.setBrush(
                    COLORS["hover"]
                )
            else:
                painter.setBrush(
                    QColor(
                        COLORS["pink"] if i % 2 == 0
                        else COLORS["purple"]
                    )
                )

            painter.setPen(
                QPen(
                    QColor(255, 255, 255, alpha),
                    1.5
                )
            )

            r = ITEM_RADIUS + (3 if hovered else 0)

            painter.drawEllipse(
                pos,
                r,
                r
            )

            # Icons
            painter.setPen(
                QColor(91, 69, 105, alpha)
            )

            painter.setFont(
                QFont("DejaVu Sans", 13, QFont.Weight.Bold)
            )

            painter.drawText(
                QRectF(
                    pos.x() - 18,
                    pos.y() - 16,
                    36,
                    32
                ),
                Qt.AlignmentFlag.AlignCenter,
                ICONS[i]
            )

            # Labels
            if self.progress > 0.88:

                painter.setFont(
                    QFont("Noto Sans", 8)
                )

                painter.setPen(
                    QColor(72, 58, 78, alpha)
                )

                label = self.LABELS[i]

                if i == 0:
                    label = f"Wi-Fi: {self.wifi}"

                elif i == 1:
                    label = f"BT: {self.bluetooth}"

                elif i == 4:
                    label = self.battery

                painter.drawText(
                    QRectF(
                        pos.x() - 41,
                        pos.y() + 30,
                        82,
                        20
                    ),
                    Qt.AlignmentFlag.AlignCenter,
                    label
                )

        # Feedback message
        if self.status_message:

            painter.setPen(
                QColor(91, 69, 105, alpha)
            )

            painter.setFont(
                QFont("Noto Sans", 9)
            )

            painter.drawText(
                QRectF(65, 390, 290, 20),
                Qt.AlignmentFlag.AlignCenter,
                self.status_message
            )

    def draw_center_orb(self, painter):

        # Soft shadow
        painter.setPen(Qt.PenStyle.NoPen)

        painter.setBrush(
            QColor(120, 90, 130, 35)
        )

        painter.drawEllipse(
            QPointF(
                CENTER.x() + 2,
                CENTER.y() + 4
            ),
            ORB_RADIUS + 2,
            ORB_RADIUS + 2
        )

        # Main orb
        painter.setPen(
            QPen(
                QColor(255, 255, 255, 240),
                2
            )
        )

        painter.setBrush(
            COLORS["orb"]
        )

        painter.drawEllipse(
            CENTER,
            ORB_RADIUS,
            ORB_RADIUS
        )

        # Flower icon
        painter.setPen(
            COLORS["dark"]
        )

        painter.setFont(
            QFont(
                "Noto Sans",
                21,
                QFont.Weight.Bold
            )
        )

        painter.drawText(
            QRectF(
                CENTER.x() - 25,
                CENTER.y() - 23,
                50,
                46
            ),
            Qt.AlignmentFlag.AlignCenter,
            "✿"
        )

    # --------------------------------------------------
    # MOUSE INTERACTION
    # --------------------------------------------------

    
def mouseMoveEvent(self, event):

    pos = QPointF(event.position())

    # Dragging the centre orb
    if self.drag_origin is not None:

        delta = (
            event.globalPosition().toPoint()
            - self.drag_origin
        )

        self.move(self.window_origin + delta)
        return

    distance = self.distance(pos, CENTER)

    # Keep the menu open while the cursor
    # moves inside the radial control area.
    inside_orb = distance < ORB_RADIUS + 12

    inside_menu = (
        self.expanded and distance < 190
    )

    self.set_expanded(
        inside_orb or inside_menu
    )

    # Only detect button hovering after
    # the animation has completed.
    self.hover_index = -1

    if self.progress > 0.95:

        for i, point in enumerate(self.target_positions()):

            if self.distance(pos, point) < ITEM_RADIUS + 12:
                self.hover_index = i
                break

    if self.hover_index >= 0:
        self.setCursor(Qt.CursorShape.PointingHandCursor)
    else:
        self.unsetCursor()

    self.update()


def leaveEvent(self, event):

    self.hover_index = -1
    self.pressed_index = -1
    self.set_expanded(False)
    self.unsetCursor()


def mousePressEvent(self, event):

    pos = QPointF(event.position())

    if event.button() == Qt.MouseButton.RightButton:

        self.context_menu(
            event.globalPosition().toPoint()
        )

        return

    if event.button() != Qt.MouseButton.LeftButton:
        return

    # Detect radial button clicks first.
    if self.progress > 0.95:

        for i, point in enumerate(self.target_positions()):

            if self.distance(pos, point) < ITEM_RADIUS + 12:

                self.pressed_index = i
                return

    # Centre orb: dragging or expanding.
    if self.distance(pos, CENTER) < ORB_RADIUS + 12:

        self.drag_origin = (
            event.globalPosition().toPoint()
        )

        self.window_origin = self.pos()


def mouseReleaseEvent(self, event):

    if event.button() != Qt.MouseButton.LeftButton:
        return

    pos = QPointF(event.position())

    # Handle radial button click.
    if self.pressed_index >= 0:

        index = self.pressed_index
        self.pressed_index = -1

        if self.progress > 0.95:

            point = self.target_positions()[index]

            if self.distance(pos, point) < ITEM_RADIUS + 12:
                self.activate(index)

        return

    # Handle centre orb dragging.
    if self.drag_origin is not None:

        moved = (
            event.globalPosition().toPoint()
            - self.drag_origin
        ).manhattanLength() > 5

        self.drag_origin = None

        if moved:
            self.save_position()

        else:
            self.set_expanded(not self.expanded)

        return


    def leaveEvent(self, event):

        self.hover_index = -1
        self.set_expanded(False)
        self.unsetCursor()

    def mousePressEvent(self, event):

        pos = QPointF(event.position())

        if event.button() == Qt.MouseButton.RightButton:

            self.context_menu(
                event.globalPosition().toPoint()
            )

            return

        if event.button() == Qt.MouseButton.LeftButton:

            if self.distance(pos, CENTER) < ORB_RADIUS + 10:

                self.drag_origin = (
                    event.globalPosition().toPoint()
                )

                self.window_origin = self.pos()

                self.setCursor(
                    Qt.CursorShape.ClosedHandCursor
                )

    def mouseReleaseEvent(self, event):

        if event.button() != Qt.MouseButton.LeftButton:
            return

        if self.drag_origin is not None:

            moved = (
                event.globalPosition().toPoint()
                - self.drag_origin
            ).manhattanLength() > 5

            self.drag_origin = None

            self.unsetCursor()

            if moved:
                self.save_position()

            else:
                self.set_expanded(
                    not self.expanded
                )

            return

        pos = QPointF(event.position())

        for i, point in enumerate(
            self.item_positions()
        ):

            if self.distance(pos, point) < ITEM_RADIUS + 10:

                self.activate(i)
                return

    # --------------------------------------------------
    # SYSTEM CONTROLS
    # --------------------------------------------------

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
            self.open_battery_info()

        elif index == 5:
            self.change_brightness("5%-")

        elif index == 6:
            self.change_brightness("5%+")

        elif index == 7:
            self.open_settings()

    def toggle_wifi(self):

        if self.wifi not in ("On", "Off"):
            self.notify("Wi-Fi status unavailable")
            return

        state = (
            "off" if self.wifi == "On"
            else "on"
        )

        self.execute(
            ["nmcli", "radio", "wifi", state],
            f"Wi-Fi {state.upper()}"
        )

    def toggle_bluetooth(self):

        if self.bluetooth not in ("On", "Off"):
            self.notify("Bluetooth unavailable")
            return

        state = (
            "off" if self.bluetooth == "On"
            else "on"
        )

        self.execute(
            ["bluetoothctl", "power", state],
            f"Bluetooth {state.upper()}"
        )

    def change_volume(self, amount):

        if has_command("pactl"):

            self.execute(
                [
                    "pactl",
                    "set-sink-volume",
                    "@DEFAULT_SINK@",
                    amount
                ],
                f"Volume {amount}"
            )

        elif has_command("wpctl"):

            self.execute(
                [
                    "wpctl",
                    "set-volume",
                    "@DEFAULT_AUDIO_SINK@",
                    amount
                ],
                f"Volume {amount}"
            )

        else:
            self.notify("Audio control unavailable")

    def change_brightness(self, amount):

        if not has_command("brightnessctl"):
            self.notify("Install brightnessctl first")
            return

        self.execute(
            [
                "brightnessctl",
                "set",
                amount
            ],
            f"Brightness {amount}"
        )

    # --------------------------------------------------
    # SETTINGS AND BATTERY
    # --------------------------------------------------

    def open_settings(self):

        desktop = os.environ.get(
            "XDG_CURRENT_DESKTOP",
            ""
        ).lower()

        if "kde" in desktop:
            candidates = [
                "systemsettings",
                "xfce4-settings-manager",
                "gnome-control-center"
            ]

        elif "xfce" in desktop:
            candidates = [
                "xfce4-settings-manager",
                "gnome-control-center",
                "systemsettings"
            ]

        elif "gnome" in desktop or "cinnamon" in desktop:
            candidates = [
                "gnome-control-center",
                "cinnamon-settings",
                "xfce4-settings-manager"
            ]

        else:
            candidates = [
                "xfce4-settings-manager",
                "systemsettings",
                "gnome-control-center",
                "cinnamon-settings"
            ]

        for app in candidates:

            executable = shutil.which(app)

            if executable:

                try:
                    subprocess.Popen(
                        [executable],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        start_new_session=True
                    )

                    self.notify("Opening settings")
                    return

                except OSError:
                    continue

        self.notify("Settings application not found")

    def open_battery_info(self):

        if has_command("xfce4-power-manager-settings"):

            executable = shutil.which(
                "xfce4-power-manager-settings"
            )

            if executable:
                subprocess.Popen(
                    [executable],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    start_new_session=True
                )

                return

        self.notify(
            f"Battery: {self.battery}"
        )

    # --------------------------------------------------
    # CONTEXT MENU
    # --------------------------------------------------

    def context_menu(self, point):

        menu = QMenu(self)

        menu.setStyleSheet("""
            QMenu {
                background-color: #fff5fa;
                color: #594563;
                border: 1px solid #e8d6ed;
                border-radius: 9px;
                padding: 6px;
            }

            QMenu::item {
                padding: 8px 24px;
                border-radius: 5px;
            }

            QMenu::item:selected {
                background-color: #e8d9f5;
            }
        """)

        refresh_action = QAction(
            "↻  Refresh status",
            menu
        )

        refresh_action.triggered.connect(
            self.refresh_status
        )

        menu.addAction(refresh_action)

        menu.addSeparator()

        reset_action = QAction(
            "⌖  Reset position",
            menu
        )

        reset_action.triggered.connect(
            self.reset_position
        )

        menu.addAction(reset_action)

        menu.addSeparator()

        quit_action = QAction(
            "✕  Quit Cozy Orbit",
            menu
        )

        quit_action.triggered.connect(
            QApplication.quit
        )

        menu.addAction(quit_action)

        menu.exec(point)

    def reset_position(self):

        try:
            POSITION_FILE.unlink(missing_ok=True)
        except OSError:
            pass

        screen = QApplication.primaryScreen()

        if screen:

            geometry = screen.availableGeometry()

            self.move(
                geometry.right() - SIZE - 35,
                geometry.bottom() - SIZE - 65
            )

            self.save_position()

    # --------------------------------------------------
    # CLEANUP
    # --------------------------------------------------

    def closeEvent(self, event):

        self.timer.stop()
        self.anim.stop()

        self.save_position()

        event.accept()

    def target_positions(self):

    positions = []

    for i in range(8):
        angle = math.radians(-90 + i * 45)

        positions.append(
            QPointF(
                CENTER.x() + math.cos(angle) * ORBIT_RADIUS,
                CENTER.y() + math.sin(angle) * ORBIT_RADIUS
            )
        )

    return positions


# --------------------------------------------------
# APPLICATION ENTRY
# --------------------------------------------------

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
            f"{APP_NAME} failed: {exc}",
            file=sys.stderr
        )

        raise
