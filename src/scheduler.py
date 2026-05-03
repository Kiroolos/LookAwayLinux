from __future__ import annotations

from PyQt6.QtCore import QObject, QTimer, pyqtSignal

from .config import Settings
from .idle import IdleMonitor


class BreakScheduler(QObject):
    """One-second-tick scheduler for breaks, blinks, posture, idle pauses."""

    break_due = pyqtSignal(bool)
    blink_due = pyqtSignal()
    posture_due = pyqtSignal()
    state_changed = pyqtSignal()

    def __init__(self, settings: Settings, idle: IdleMonitor) -> None:
        super().__init__()
        self._settings = settings
        self._idle = idle
        self._work_seconds = 0
        self._blink_seconds = 0
        self._posture_seconds = 0
        self._completed_breaks_today = 0
        self._paused_until_timer: QTimer | None = None
        self._paused = False
        self._was_idle = False
        self._suspended = False
        self._tick = QTimer(self)
        self._tick.setInterval(1000)
        self._tick.timeout.connect(self._on_tick)

    def update_settings(self, settings: Settings) -> None:
        self._settings = settings
        self.state_changed.emit()

    def start(self) -> None:
        self._tick.start()

    def stop(self) -> None:
        self._tick.stop()

    def is_paused(self) -> bool:
        return self._paused

    def is_suspended(self) -> bool:
        return self._suspended

    def seconds_until_break(self) -> int:
        target = self._settings.work_minutes * 60
        return max(0, target - self._work_seconds)

    def seconds_into_work(self) -> int:
        return self._work_seconds

    def is_long_break_next(self) -> bool:
        return self._settings.long_break_every > 0 and (
            (self._completed_breaks_today + 1) % self._settings.long_break_every == 0
        )

    def force_break(self, long: bool | None = None) -> None:
        is_long = self.is_long_break_next() if long is None else long
        self.break_due.emit(is_long)

    def reset_after_break(self, completed: bool) -> None:
        self._work_seconds = 0
        self._blink_seconds = 0
        self._posture_seconds = 0
        if completed:
            self._completed_breaks_today += 1
        self.state_changed.emit()

    def snooze(self, seconds: int) -> None:
        self._work_seconds = max(0, self._settings.work_minutes * 60 - seconds)
        self.state_changed.emit()

    def pause(self, minutes: int | None = None) -> None:
        if self._paused_until_timer:
            self._paused_until_timer.stop()
            self._paused_until_timer = None
        self._paused = True
        if minutes:
            self._paused_until_timer = QTimer(self)
            self._paused_until_timer.setSingleShot(True)
            self._paused_until_timer.timeout.connect(self.resume)
            self._paused_until_timer.start(minutes * 60 * 1000)
        self.state_changed.emit()

    def resume(self) -> None:
        if self._paused_until_timer:
            self._paused_until_timer.stop()
            self._paused_until_timer = None
        self._paused = False
        self.state_changed.emit()

    def suspend(self) -> None:
        self._suspended = True

    def unsuspend(self) -> None:
        self._suspended = False

    def reset_day_counters(self) -> None:
        self._completed_breaks_today = 0

    def completed_breaks_today(self) -> int:
        return self._completed_breaks_today

    def _on_tick(self) -> None:
        if self._suspended:
            return
        idle_s = self._idle.idle_seconds()
        idle_threshold = max(5, self._settings.idle_pause_seconds)
        currently_idle = idle_s >= idle_threshold

        if currently_idle and not self._was_idle:
            self._was_idle = True
            self.state_changed.emit()
        elif not currently_idle and self._was_idle:
            self._was_idle = False
            if idle_s >= idle_threshold * 0.8:
                self._work_seconds = 0
                self._blink_seconds = 0
                self._posture_seconds = 0
            self.state_changed.emit()

        if self._paused or currently_idle:
            return

        self._work_seconds += 1
        self._blink_seconds += 1
        self._posture_seconds += 1

        if self._work_seconds >= self._settings.work_minutes * 60:
            self._work_seconds = 0
            self._blink_seconds = 0
            self._posture_seconds = 0
            self.break_due.emit(self.is_long_break_next())
            return

        if (
            self._settings.blink_reminder_enabled
            and self._blink_seconds >= self._settings.blink_reminder_minutes * 60
        ):
            self._blink_seconds = 0
            self.blink_due.emit()

        if (
            self._settings.posture_reminder_enabled
            and self._posture_seconds >= self._settings.posture_reminder_minutes * 60
        ):
            self._posture_seconds = 0
            self.posture_due.emit()

        self.state_changed.emit()
