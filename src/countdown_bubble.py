from __future__ import annotations

from typing import Callable

from PyQt6.QtCore import QPoint, QRect, Qt, QTimer
from PyQt6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QGuiApplication,
    QMouseEvent,
    QPainter,
    QPainterPath,
    QPen,
)
from PyQt6.QtWidgets import QWidget


class CountdownBubble(QWidget):
    """Always-on-top pill showing time until next break.

    Drag to move. Click anywhere to trigger a break now (configurable hook).
    """

    _W = 140
    _H = 30

    def __init__(
        self,
        get_remaining: Callable[[], int],
        get_paused: Callable[[], bool],
        get_long_next: Callable[[], bool],
        on_click: Callable[[], None],
    ) -> None:
        super().__init__()
        self._get_remaining = get_remaining
        self._get_paused = get_paused
        self._get_long_next = get_long_next
        self._on_click = on_click
        self._drag_origin: QPoint | None = None
        self._dragging = False

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowDoesNotAcceptFocus
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setFixedSize(self._W, self._H)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip("Click to take a break now · drag to move")

        self._tick = QTimer(self)
        self._tick.setInterval(500)
        self._tick.timeout.connect(self.update)

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.rect().adjusted(0, 0, -1, -1)
        path = QPainterPath()
        path.addRoundedRect(float(rect.x()), float(rect.y()), float(rect.width()), float(rect.height()), 14.0, 14.0)
        paused = self._get_paused()
        if paused:
            bg = QColor(50, 35, 35, 220)
            border = QColor(255, 180, 180, 60)
        else:
            bg = QColor(20, 22, 30, 220)
            border = QColor(255, 255, 255, 36)
        p.fillPath(path, QBrush(bg))
        p.setPen(QPen(border, 1))
        p.drawPath(path)

        f = QFont()
        f.setPixelSize(13)
        f.setWeight(QFont.Weight.DemiBold)
        p.setFont(f)
        p.setPen(QPen(QColor(255, 255, 255, 235)))
        if paused:
            label = "❚❚  paused"
        else:
            secs = max(0, self._get_remaining())
            mins, s = divmod(secs, 60)
            kind = "long" if self._get_long_next() else "next"
            label = f"●  {kind} {mins:02d}:{s:02d}"
        p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, label)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() != Qt.MouseButton.LeftButton:
            return
        self._drag_origin = event.globalPosition().toPoint() - self.pos()
        self._dragging = False

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._drag_origin is None:
            return
        new_pos = event.globalPosition().toPoint() - self._drag_origin
        if not self._dragging and (event.globalPosition().toPoint() - (self._drag_origin + self.pos())).manhattanLength() > 4:
            self._dragging = True
        if self._dragging:
            self.move(new_pos)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() != Qt.MouseButton.LeftButton:
            return
        was_dragging = self._dragging
        self._drag_origin = None
        self._dragging = False
        if not was_dragging:
            self._on_click()

    def show_at_default_corner(self) -> None:
        screen = QGuiApplication.primaryScreen()
        if screen is None:
            self.show()
            return
        geom: QRect = screen.availableGeometry()
        margin = 16
        self.move(geom.right() - self._W - margin, geom.top() + margin)
        self.show()
        self.raise_()
        self._tick.start()

    def hide_bubble(self) -> None:
        self._tick.stop()
        self.hide()
