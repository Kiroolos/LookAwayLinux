from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from PyQt6.QtCore import (
    QEasingCurve,
    QPoint,
    QPropertyAnimation,
    QRect,
    Qt,
    QTimer,
    pyqtSignal,
)
from PyQt6.QtGui import (
    QBrush,
    QColor,
    QCursor,
    QFont,
    QGuiApplication,
    QPainter,
    QPainterPath,
    QPen,
)
from PyQt6.QtWidgets import (
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)


@dataclass
class ReminderRequest:
    title: str
    subtitle: str
    glyph: str
    accent: str = "#7BA8FF"
    duration_ms: int = 6000
    near_cursor: bool = False


class _Glyph(QWidget):
    def __init__(self, glyph: str, accent: str, parent: QWidget) -> None:
        super().__init__(parent)
        self._glyph = glyph
        self._accent = QColor(accent)
        self.setFixedSize(56, 56)

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        c = self._accent
        p.setPen(Qt.PenStyle.NoPen)
        bg = QColor(c)
        bg.setAlpha(48)
        p.setBrush(QBrush(bg))
        p.drawEllipse(self.rect().adjusted(2, 2, -2, -2))
        f = QFont()
        f.setPixelSize(28)
        f.setBold(True)
        p.setFont(f)
        p.setPen(QPen(c))
        p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, self._glyph)


class MiniReminder(QWidget):
    """Frameless rounded popup that slides in, plays a chime, auto-dismisses."""

    closed = pyqtSignal()

    _W = 360
    _H = 116

    def __init__(self, request: ReminderRequest) -> None:
        super().__init__()
        self._request = request
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowDoesNotAcceptFocus
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.resize(self._W, self._H)

        outer = QHBoxLayout(self)
        outer.setContentsMargins(20, 16, 20, 16)
        outer.setSpacing(16)

        glyph = _Glyph(request.glyph, request.accent, self)
        outer.addWidget(glyph, 0, Qt.AlignmentFlag.AlignVCenter)

        text_col = QVBoxLayout()
        text_col.setSpacing(2)
        title = QLabel(request.title)
        title_font = QFont()
        title_font.setPixelSize(15)
        title_font.setWeight(QFont.Weight.DemiBold)
        title.setFont(title_font)
        title.setStyleSheet("color: rgba(255,255,255,235);")
        text_col.addWidget(title)
        subtitle = QLabel(request.subtitle)
        sub_font = QFont()
        sub_font.setPixelSize(12)
        subtitle.setFont(sub_font)
        subtitle.setWordWrap(True)
        subtitle.setStyleSheet("color: rgba(255,255,255,170);")
        text_col.addWidget(subtitle)
        outer.addLayout(text_col, 1)

        self._opacity = QGraphicsOpacityEffect(self)
        self._opacity.setOpacity(0.0)
        self.setGraphicsEffect(self._opacity)

        self._fade_in = QPropertyAnimation(self._opacity, b"opacity", self)
        self._fade_in.setDuration(280)
        self._fade_in.setStartValue(0.0)
        self._fade_in.setEndValue(1.0)
        self._fade_in.setEasingCurve(QEasingCurve.Type.OutCubic)

        self._fade_out = QPropertyAnimation(self._opacity, b"opacity", self)
        self._fade_out.setDuration(360)
        self._fade_out.setStartValue(1.0)
        self._fade_out.setEndValue(0.0)
        self._fade_out.setEasingCurve(QEasingCurve.Type.InCubic)
        self._fade_out.finished.connect(self._on_fade_out_done)

        self._slide = QPropertyAnimation(self, b"pos", self)
        self._slide.setDuration(320)
        self._slide.setEasingCurve(QEasingCurve.Type.OutBack)

        self._dismiss_timer = QTimer(self)
        self._dismiss_timer.setSingleShot(True)
        self._dismiss_timer.timeout.connect(self.dismiss)

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.rect().adjusted(0, 0, -1, -1)
        path = QPainterPath()
        path.addRoundedRect(float(rect.x()), float(rect.y()), float(rect.width()), float(rect.height()), 18.0, 18.0)
        p.setPen(Qt.PenStyle.NoPen)
        bg = QColor(18, 22, 32, 235)
        p.fillPath(path, QBrush(bg))
        p.setPen(QPen(QColor(255, 255, 255, 24), 1))
        p.drawPath(path)

    def mousePressEvent(self, _event) -> None:
        self.dismiss()

    def show_at(self, target_pos: QPoint) -> None:
        start_pos = QPoint(target_pos.x(), target_pos.y() + 24)
        self.move(start_pos)
        self.show()
        self.raise_()
        self._slide.stop()
        self._slide.setStartValue(start_pos)
        self._slide.setEndValue(target_pos)
        self._slide.start()
        self._fade_in.start()
        self._dismiss_timer.start(self._request.duration_ms)

    def dismiss(self) -> None:
        if self._fade_out.state() == QPropertyAnimation.State.Running:
            return
        self._dismiss_timer.stop()
        self._fade_in.stop()
        self._fade_out.start()

    def _on_fade_out_done(self) -> None:
        self.hide()
        self.closed.emit()
        self.deleteLater()


def compute_position(request: ReminderRequest, w: int, h: int, margin: int = 24) -> QPoint:
    """Pick a screen-aware position: near cursor (clamped) or top-right of cursor's screen."""
    screens = QGuiApplication.screens()
    if not screens:
        return QPoint(margin, margin)
    cursor = QCursor.pos()
    target_screen = QGuiApplication.screenAt(cursor) or QGuiApplication.primaryScreen()
    geom: QRect = target_screen.availableGeometry()
    if request.near_cursor:
        x = cursor.x() + 16
        y = cursor.y() + 16
        if x + w > geom.right() - margin:
            x = cursor.x() - w - 16
        if y + h > geom.bottom() - margin:
            y = cursor.y() - h - 16
        x = max(geom.left() + margin, min(x, geom.right() - w - margin))
        y = max(geom.top() + margin, min(y, geom.bottom() - h - margin))
        return QPoint(x, y)
    return QPoint(geom.right() - w - margin, geom.top() + margin)


class MiniReminderManager:
    """Coordinates a single visible reminder; queues replacements to avoid stacks."""

    def __init__(self) -> None:
        self._current: MiniReminder | None = None

    def show(self, request: ReminderRequest, on_close: Callable[[], None] | None = None) -> MiniReminder:
        if self._current is not None:
            try:
                self._current.dismiss()
            except RuntimeError:
                pass
            self._current = None
        reminder = MiniReminder(request)
        pos = compute_position(request, reminder._W, reminder._H)
        reminder.closed.connect(lambda: self._on_closed(reminder, on_close))
        reminder.show_at(pos)
        self._current = reminder
        return reminder

    def _on_closed(self, reminder: MiniReminder, on_close: Callable[[], None] | None) -> None:
        if self._current is reminder:
            self._current = None
        if on_close is not None:
            on_close()

    def dismiss_all(self) -> None:
        if self._current is not None:
            try:
                self._current.dismiss()
            except RuntimeError:
                pass
            self._current = None
