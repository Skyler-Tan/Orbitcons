#!/usr/bin/env python3
"""Cozy Orbit v0.3.1: mask-free Qt floating radial controls."""
import math
import os
import subprocess
import sys
from pathlib import Path

from PySide6.QtCore import QPoint, QPointF, Qt, QTimer
from PySide6.QtGui import QAction, QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QApplication, QMenu, QWidget

APP_DIR = Path.home() / ".local/share/cozy-orbit"
APP_DIR.mkdir(parents=True, exist_ok=True)
POSITION_FILE = APP_DIR / "position"


def command(args, timeout=3):
    try:
        return subprocess.run(args, capture_output=True, text=True, timeout=timeout, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return None


def output(args, fallback=""):
    result = command(args)
    return result.stdout.strip() if result and result.returncode == 0 else fallback


class CozyOrbit(QWidget):
    SIZE = 360
    CENTER = QPointF(180, 180)
    ORB_R = 31
    ITEM_R = 25
    LABELS = ["Wi-Fi", "Bluetooth", "Volume −", "Volume +", "Battery", "Brightness −", "Brightness +", "Settings"]
    ICONS = ["⌁", "ᛒ", "−", "+", "♡", "☾", "☼", "⚙"]

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Cozy Orbit")
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        self.setFixedSize(self.SIZE, self.SIZE)
        self.expanded = False
        self.progress = 0.0
        self.drag_origin = None
        self.window_origin = None
        self.hover_index = -1
        self.wifi = self.bluetooth = "?"
        self.battery = "—"
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh_status)
        self.timer.start(2500)
        self.anim = QTimer(self)
        self.anim.setInterval(16)
        self.anim.timeout.connect(self.animate)
        self.restore_position()
        self.refresh_status()

    def restore_position(self):
        try:
            x, y = map(int, POSITION_FILE.read_text().split())
            self.move(x, y)
        except (OSError, ValueError):
            screen = QApplication.primaryScreen().availableGeometry()
            self.move(screen.right() - self.SIZE - 40, screen.bottom() - self.SIZE - 80)

    def save_position(self):
        try:
            POSITION_FILE.write_text(f"{self.x()} {self.y()}\n")
        except OSError:
            pass

    def refresh_status(self):
        self.wifi = output(["nmcli", "-t", "-f", "WIFI", "general"], "?")
        bt = output(["bluetoothctl", "show"], "")
        self.bluetooth = "On" if "Powered: yes" in bt else "Off" if "Powered: no" in bt else "?"
        cap = output(["sh", "-c", "for f in /sys/class/power_supply/BAT*/capacity; do cat \"$f\"; exit; done"], "")
        self.battery = cap + "%" if cap.isdigit() else "—"
        self.update()

    def animate(self):
        target = 1.0 if self.expanded else 0.0
        delta = target - self.progress
        self.progress = target if abs(delta) < .025 else self.progress + delta * .22
        self.update()
        if self.progress == target:
            self.anim.stop()

    def set_expanded(self, state):
        if self.expanded == state:
            return
        self.expanded = state
        self.anim.start()

    def item_positions(self):
        # Stable positions; only painting changes during animation (no masks or resize).
        points = []
        for i in range(8):
            angle = math.radians(-90 + i * 45)
            radius = 117 * self.progress
            spin = (1.0 - self.progress) * math.radians(95)
            points.append(QPointF(self.CENTER.x() + math.cos(angle + spin) * radius,
                                  self.CENTER.y() + math.sin(angle + spin) * radius))
        return points

    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        # The window remains a single fixed-size translucent surface for its lifetime.
        if self.progress > 0.001:
            p.setPen(QPen(QColor(255, 255, 255, 95), 1.3))
            p.setBrush(QColor(255, 246, 252, int(90 * self.progress)))
            p.drawEllipse(self.CENTER, 145 * self.progress, 145 * self.progress)
            for i, pos in enumerate(self.item_positions()):
                alpha = int(255 * min(1, self.progress * 1.8))
                p.setPen(QPen(QColor(255, 255, 255, 210), 1.2))
                p.setBrush(QColor(213, 196, 246, alpha) if i % 2 else QColor(255, 210, 224, alpha))
                p.drawEllipse(pos, self.ITEM_R, self.ITEM_R)
                p.setPen(QColor(91, 69, 105, alpha))
                p.setFont(QFont("Noto Sans", 13, QFont.Weight.DemiBold))
                p.drawText(pos.x() - 15, pos.y() - 12, 30, 24, Qt.AlignmentFlag.AlignCenter, self.ICONS[i])
                if self.progress > .88:
                    p.setFont(QFont("Noto Sans", 8))
                    p.setPen(QColor(72, 58, 78, alpha))
                    label = self.LABELS[i]
                    if i == 0: label = f"Wi-Fi {self.wifi}"
                    if i == 1: label = f"BT {self.bluetooth}"
                    if i == 4: label = self.battery
                    p.drawText(pos.x() - 39, pos.y() + 31, 78, 18, Qt.AlignmentFlag.AlignCenter, label)
        p.setPen(QPen(QColor(255, 255, 255, 235), 2))
        p.setBrush(QColor(255, 206, 222, 248))
        p.drawEllipse(self.CENTER, self.ORB_R, self.ORB_R)
        p.setPen(QColor(111, 77, 115))
        p.setFont(QFont("Noto Sans", 17, QFont.Weight.Bold))
        p.drawText(155, 164, 50, 34, Qt.AlignmentFlag.AlignCenter, "✿")
        p.end()

    def local_point(self, event):
        return QPointF(event.position())

    def mouseMoveEvent(self, event):
        pos = self.local_point(event)
        if self.drag_origin is not None:
            delta = event.globalPosition().toPoint() - self.drag_origin
            self.move(self.window_origin + delta)
            return
        inside_orb = (pos - self.CENTER).manhattanLength() < self.ORB_R + 9
        inside_item = any((pos - pt).manhattanLength() < self.ITEM_R + 10 for pt in self.item_positions()) if self.progress > .15 else False
        self.set_expanded(inside_orb or inside_item)
        self.hover_index = next((i for i, pt in enumerate(self.item_positions()) if math.hypot(pos.x()-pt.x(), pos.y()-pt.y()) < self.ITEM_R+8), -1)
        self.update()

    def leaveEvent(self, _event):
        self.hover_index = -1
        self.set_expanded(False)

    def mousePressEvent(self, event):
        pos = self.local_point(event)
        if event.button() == Qt.MouseButton.RightButton:
            self.context_menu(event.globalPosition().toPoint())
        elif event.button() == Qt.MouseButton.LeftButton and math.hypot(pos.x()-180, pos.y()-180) < self.ORB_R + 8:
            self.drag_origin = event.globalPosition().toPoint()
            self.window_origin = self.pos()

    def mouseReleaseEvent(self, event):
        if self.drag_origin is not None:
            moved = (event.globalPosition().toPoint() - self.drag_origin).manhattanLength() > 5
            self.drag_origin = None
            if moved: self.save_position()
            return
        if event.button() == Qt.MouseButton.LeftButton and self.hover_index >= 0:
            self.activate(self.hover_index)

    def context_menu(self, point):
        menu = QMenu(self)
        quit_action = QAction("Quit Cozy Orbit", menu)
        quit_action.triggered.connect(QApplication.quit)
        menu.addAction(quit_action)
        menu.exec(point)

    def activate(self, i):
        if i == 0:
            state = "off" if self.wifi.lower() == "enabled" else "on"
            command(["nmcli", "radio", "wifi", state])
        elif i == 1:
            command(["bluetoothctl", "power", "off" if self.bluetooth == "On" else "on"])
        elif i in (2, 3):
            command(["pactl", "set-sink-volume", "@DEFAULT_SINK@", "-5%" if i == 2 else "+5%"])
        elif i in (5, 6):
            command(["brightnessctl", "set", "5%-" if i == 5 else "+5%"])
        elif i == 7:
            command(["systemsettings"])
        self.refresh_status()


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Cozy Orbit")
    widget = CozyOrbit()
    widget.show()
    return app.exec()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"Cozy Orbit failed to start: {exc}", file=sys.stderr)
        raise
