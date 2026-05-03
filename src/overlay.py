from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Callable

from PyQt6.QtCore import (
    QEasingCurve,
    QPropertyAnimation,
    QRectF,
    Qt,
    QTimer,
    pyqtSignal,
)
from PyQt6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QFontDatabase,
    QGuiApplication,
    QKeySequence,
    QPainter,
    QPaintEvent,
    QPen,
    QRadialGradient,
    QShortcut,
)
from PyQt6.QtWidgets import (
    QApplication,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


@dataclass
class BreakRequest:
    duration_s: int
    long_break: bool
    enforce: str
    show_countdown: bool
    can_snooze: bool


class _AnimatedBackground(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._phase = 0.0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(33)

    def _tick(self) -> None:
        self._phase = (self._phase + 0.005) % 1.0
        self.update()

    def paintEvent(self, _event: QPaintEvent) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.rect()
        bg = QColor(8, 12, 20)
        p.fillRect(rect, bg)
        cx = rect.width() / 2 + math.sin(self._phase * 2 * math.pi) * rect.width() * 0.18
        cy = rect.height() / 2 + math.cos(self._phase * 2 * math.pi) * rect.height() * 0.14
        radius = max(rect.width(), rect.height())
        grad = QRadialGradient(cx, cy, radius)
        grad.setColorAt(0.0, QColor(60, 110, 200, 180))
        grad.setColorAt(0.4, QColor(30, 60, 130, 80))
        grad.setColorAt(1.0, QColor(8, 12, 20, 0))
        p.fillRect(rect, QBrush(grad))
        cx2 = rect.width() / 2 - math.cos(self._phase * 2 * math.pi) * rect.width() * 0.22
        cy2 = rect.height() / 2 - math.sin(self._phase * 2 * math.pi) * rect.height() * 0.18
        grad2 = QRadialGradient(cx2, cy2, radius * 0.8)
        grad2.setColorAt(0.0, QColor(140, 80, 200, 120))
        grad2.setColorAt(0.5, QColor(80, 40, 140, 50))
        grad2.setColorAt(1.0, QColor(8, 12, 20, 0))
        p.fillRect(rect, QBrush(grad2))


class BreakWindow(QWidget):
    """Full-screen break overlay covering one screen."""

    skipped = pyqtSignal()
    snoozed = pyqtSignal()
    finished = pyqtSignal()

    def __init__(self, screen, primary: bool, request: BreakRequest, get_remaining: Callable[[], int]) -> None:
        super().__init__()
        self._screen = screen
        self._primary = primary
        self._request = request
        self._get_remaining = get_remaining

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
            | Qt.WindowType.X11BypassWindowManagerHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, False)
        self.setCursor(Qt.CursorShape.BlankCursor)
        self.setGeometry(screen.geometry())

        self._bg = _AnimatedBackground(self)
        self._bg.setGeometry(self.rect())

        self._build_ui()

        self._fade = QGraphicsOpacityEffect(self)
        self._fade.setOpacity(0.0)
        self.setGraphicsEffect(self._fade)
        self._anim = QPropertyAnimation(self._fade, b"opacity", self)
        self._anim.setDuration(700)
        self._anim.setStartValue(0.0)
        self._anim.setEndValue(1.0)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)

        self._tick_timer = QTimer(self)
        self._tick_timer.timeout.connect(self._refresh)
        self._tick_timer.start(250)

        QShortcut(QKeySequence("Esc"), self, activated=self._on_skip)

    def resizeEvent(self, event) -> None:
        self._bg.setGeometry(self.rect())
        super().resizeEvent(event)

    def _build_ui(self) -> None:
        if not self._primary:
            return
        outer = QVBoxLayout(self)
        outer.setContentsMargins(80, 80, 80, 80)
        outer.setSpacing(12)
        outer.addStretch(1)

        title = QLabel("Look Away")
        title.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        title.setStyleSheet("color: rgba(255,255,255,230); letter-spacing: 2px;")
        title_font = self._serif_font(54)
        title.setFont(title_font)
        outer.addWidget(title)

        self._subtitle = QLabel(self._subtitle_text())
        self._subtitle.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        self._subtitle.setStyleSheet("color: rgba(255,255,255,170);")
        self._subtitle.setFont(self._sans_font(20))
        outer.addWidget(self._subtitle)

        self._countdown = QLabel("")
        self._countdown.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        self._countdown.setStyleSheet("color: rgba(255,255,255,255); margin-top: 32px;")
        self._countdown.setFont(self._sans_font(120, bold=True))
        outer.addWidget(self._countdown)

        outer.addStretch(1)

        button_row = QHBoxLayout()
        button_row.setSpacing(16)
        button_row.addStretch(1)

        self._snooze_btn = self._make_button("Snooze 5 min")
        self._snooze_btn.clicked.connect(self._on_snooze)
        if not self._request.can_snooze:
            self._snooze_btn.setEnabled(False)
            self._snooze_btn.setToolTip("Snooze limit reached for today")
        button_row.addWidget(self._snooze_btn)

        self._skip_btn = self._make_button("Skip")
        self._skip_btn.clicked.connect(self._on_skip)
        if self._request.enforce == "strict":
            self._skip_btn.setEnabled(False)
            self._skip_btn.setToolTip("Strict mode: skipping is disabled")
        button_row.addWidget(self._skip_btn)

        button_row.addStretch(1)
        outer.addLayout(button_row)

        hint = QLabel("Esc to skip — when allowed")
        hint.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        hint.setStyleSheet("color: rgba(255,255,255,90); margin-top: 18px;")
        hint.setFont(self._sans_font(12))
        outer.addWidget(hint)

    def _subtitle_text(self) -> str:
        if self._request.long_break:
            return "Take a longer break. Stand up, stretch, hydrate."
        return "Look at something 20 feet away for 20 seconds."

    def _make_button(self, text: str) -> QPushButton:
        btn = QPushButton(text)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setFont(self._sans_font(14))
        btn.setMinimumSize(180, 48)
        btn.setStyleSheet(
            """
            QPushButton {
                background: rgba(255,255,255,18);
                color: rgba(255,255,255,235);
                border: 1px solid rgba(255,255,255,40);
                border-radius: 24px;
                padding: 10px 20px;
            }
            QPushButton:hover { background: rgba(255,255,255,32); }
            QPushButton:pressed { background: rgba(255,255,255,12); }
            QPushButton:disabled { color: rgba(255,255,255,80); border-color: rgba(255,255,255,20); }
            """
        )
        return btn

    @staticmethod
    def _sans_font(px: int, bold: bool = False) -> QFont:
        f = QFont()
        f.setPixelSize(px)
        if bold:
            f.setWeight(QFont.Weight.DemiBold)
        return f

    @staticmethod
    def _serif_font(px: int) -> QFont:
        from .config import asset_dir
        font_path = asset_dir() / "fonts" / "InstrumentSerif-Italic.ttf"
        family: str | None = None
        if font_path.exists():
            fid = QFontDatabase.addApplicationFont(str(font_path))
            if fid >= 0:
                fams = QFontDatabase.applicationFontFamilies(fid)
                if fams:
                    family = fams[0]
        f = QFont(family) if family else QFont()
        f.setPixelSize(px)
        f.setItalic(True)
        return f

    def show_overlay(self) -> None:
        self.showFullScreen()
        self.raise_()
        self.activateWindow()
        self._anim.start()

    def _on_skip(self) -> None:
        if not self._skip_btn or not self._skip_btn.isEnabled():
            return
        self.skipped.emit()

    def _on_snooze(self) -> None:
        if not self._snooze_btn or not self._snooze_btn.isEnabled():
            return
        self.snoozed.emit()

    def _refresh(self) -> None:
        if not self._primary:
            return
        remaining = max(0, self._get_remaining())
        if self._request.show_countdown:
            mins, secs = divmod(remaining, 60)
            self._countdown.setText(f"{mins:02d}:{secs:02d}")
        else:
            self._countdown.setText("")
        if remaining <= 0:
            self.finished.emit()


class OverlayController:
    """Manages a set of BreakWindow instances across all screens."""

    def __init__(self) -> None:
        self._windows: list[BreakWindow] = []

    def show(self, request: BreakRequest, get_remaining: Callable[[], int]) -> tuple[BreakWindow, list[BreakWindow]]:
        self.close()
        screens = QGuiApplication.screens()
        if not screens:
            screens = [QGuiApplication.primaryScreen()]
        primary_screen = QGuiApplication.primaryScreen()
        primary_window: BreakWindow | None = None
        for screen in screens:
            is_primary = screen is primary_screen and primary_window is None
            win = BreakWindow(screen, is_primary, request, get_remaining)
            self._windows.append(win)
            if is_primary:
                primary_window = win
            win.show_overlay()
        if primary_window is None and self._windows:
            primary_window = self._windows[0]
        assert primary_window is not None
        others = [w for w in self._windows if w is not primary_window]
        return primary_window, others

    def close(self) -> None:
        for w in self._windows:
            try:
                w.close()
            except RuntimeError:
                pass
        self._windows.clear()
