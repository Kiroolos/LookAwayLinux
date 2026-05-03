from __future__ import annotations

import os
import shutil
import signal
import subprocess
import sys
from pathlib import Path

from PyQt6.QtCore import QSize, QTimer, qInstallMessageHandler, QtMsgType
from PyQt6.QtGui import QAction, QIcon
from PyQt6.QtWidgets import QApplication, QMenu, QMessageBox, QStyle, QSystemTrayIcon


def _qt_message_filter(mode, _ctx, msg: str) -> None:
    if "QColorSpace attempted constructed from invalid primaries" in msg:
        return
    if mode == QtMsgType.QtFatalMsg:
        sys.stderr.write(f"[qt-fatal] {msg}\n")
    elif mode == QtMsgType.QtCriticalMsg:
        sys.stderr.write(f"[qt-critical] {msg}\n")
    elif mode == QtMsgType.QtWarningMsg:
        sys.stderr.write(f"[qt-warning] {msg}\n")

from .audio import play_async
from .config import CONFIG_DIR, Settings, asset_dir, sound_path
from .idle import IdleMonitor
from .overlay import BreakRequest, OverlayController
from .scheduler import BreakScheduler
from .settings_dialog import SettingsDialog
from .stats import Stats


APP_NAME = "LookAway for Linux"
APP_ID = "lookaway-linux"


class LookAwayApp:
    def __init__(self, qapp: QApplication) -> None:
        self._qapp = qapp
        self._settings = Settings.load()
        self._stats = Stats()
        self._idle = IdleMonitor()
        self._scheduler = BreakScheduler(self._settings, self._idle)
        self._overlay = OverlayController()
        self._break_state: dict | None = None
        self._screen_time_timer = QTimer()
        self._screen_time_timer.setInterval(60_000)
        self._screen_time_timer.timeout.connect(self._record_screen_time)
        self._settings_dialog: SettingsDialog | None = None
        self._app_icon = self._load_icon()
        qapp.setWindowIcon(self._app_icon)
        qapp.setApplicationName(APP_NAME)
        qapp.setQuitOnLastWindowClosed(False)
        self._build_tray()
        self._wire_scheduler()

    def _load_icon(self) -> QIcon:
        for name in ("icon.png", "icon_ic13.png", "icon_ic07.png"):
            p = asset_dir() / "icon" / name
            if p.exists():
                return QIcon(str(p))
        return self._qapp.style().standardIcon(QStyle.StandardPixmap.SP_ComputerIcon)

    def _build_tray(self) -> None:
        self._tray = QSystemTrayIcon(self._app_icon)
        self._tray.setToolTip(APP_NAME)
        menu = QMenu()
        self._next_break_action = QAction("Next break in —")
        self._next_break_action.setEnabled(False)
        menu.addAction(self._next_break_action)
        self._status_action = QAction("Active")
        self._status_action.setEnabled(False)
        menu.addAction(self._status_action)
        menu.addSeparator()

        take_now = QAction("Take a break now", menu)
        take_now.triggered.connect(lambda: self._scheduler.force_break())
        menu.addAction(take_now)

        take_long = QAction("Take a long break now", menu)
        take_long.triggered.connect(lambda: self._scheduler.force_break(long=True))
        menu.addAction(take_long)

        menu.addSeparator()

        pause_menu = QMenu("Pause", menu)
        for label, mins in [("15 minutes", 15), ("30 minutes", 30), ("1 hour", 60), ("2 hours", 120)]:
            a = QAction(label, pause_menu)
            a.triggered.connect(lambda _checked=False, m=mins: self._pause(m))
            pause_menu.addAction(a)
        a = QAction("Until I resume", pause_menu)
        a.triggered.connect(lambda: self._pause(None))
        pause_menu.addAction(a)
        menu.addMenu(pause_menu)

        self._resume_action = QAction("Resume", menu)
        self._resume_action.triggered.connect(self._resume)
        self._resume_action.setVisible(False)
        menu.addAction(self._resume_action)

        menu.addSeparator()

        settings_action = QAction("Settings…", menu)
        settings_action.triggered.connect(self._open_settings)
        menu.addAction(settings_action)

        stats_action = QAction("Statistics…", menu)
        stats_action.triggered.connect(self._open_stats)
        menu.addAction(stats_action)

        menu.addSeparator()

        about = QAction("About", menu)
        about.triggered.connect(self._about)
        menu.addAction(about)

        quit_action = QAction("Quit", menu)
        quit_action.triggered.connect(self._quit)
        menu.addAction(quit_action)

        self._tray.setContextMenu(menu)
        self._tray.activated.connect(self._on_tray_activated)
        self._tray.show()

    def _wire_scheduler(self) -> None:
        self._scheduler.break_due.connect(self._begin_break)
        self._scheduler.blink_due.connect(self._fire_blink)
        self._scheduler.posture_due.connect(self._fire_posture)
        self._scheduler.state_changed.connect(self._refresh_tray)
        self._refresh_tray()
        self._scheduler.start()
        self._screen_time_timer.start()

    def _refresh_tray(self) -> None:
        if self._scheduler.is_paused():
            self._next_break_action.setText("Paused")
            self._status_action.setText("Click Resume to start the timer")
            self._tray.setToolTip(f"{APP_NAME} — paused")
            self._resume_action.setVisible(True)
        else:
            secs = self._scheduler.seconds_until_break()
            mins, s = divmod(secs, 60)
            label = f"{mins:02d}:{s:02d}"
            kind = "long break" if self._scheduler.is_long_break_next() else "break"
            self._next_break_action.setText(f"Next {kind} in {label}")
            done = self._scheduler.completed_breaks_today()
            self._status_action.setText(f"Completed today: {done}")
            self._tray.setToolTip(f"{APP_NAME} — next {kind} in {label}")
            self._resume_action.setVisible(False)

    def _open_settings(self) -> None:
        if self._settings_dialog and self._settings_dialog.isVisible():
            self._settings_dialog.raise_()
            self._settings_dialog.activateWindow()
            return
        dlg = SettingsDialog(self._settings, self._stats, app_icon=self._app_icon)
        dlg.settings_applied.connect(self._on_settings_applied)
        self._settings_dialog = dlg
        dlg.exec()
        self._settings_dialog = None

    def _open_stats(self) -> None:
        self._open_settings()

    def _on_settings_applied(self, settings: Settings) -> None:
        self._settings = settings
        self._scheduler.update_settings(settings)
        self._update_autostart(settings.autostart)

    def _pause(self, minutes: int | None) -> None:
        self._scheduler.pause(minutes)

    def _resume(self) -> None:
        self._scheduler.resume()

    def _begin_break(self, is_long: bool) -> None:
        if self._break_state is not None:
            return
        duration = self._settings.long_break_seconds if is_long else self._settings.break_seconds
        snoozes = self._stats.snoozes_today()
        snooze_limit = self._settings.snooze_limit_per_day
        can_snooze = self._settings.enforce_break != "strict" and (
            snooze_limit == 0 or snoozes < snooze_limit
        )
        request = BreakRequest(
            duration_s=duration,
            long_break=is_long,
            enforce=self._settings.enforce_break,
            show_countdown=self._settings.show_countdown,
            can_snooze=can_snooze,
        )
        remaining = duration

        def _get_remaining() -> int:
            return self._break_state["remaining"] if self._break_state else 0

        primary, others = self._overlay.show(request, _get_remaining)
        countdown_timer = QTimer()
        countdown_timer.setInterval(1000)

        self._break_state = {
            "remaining": remaining,
            "primary": primary,
            "others": others,
            "timer": countdown_timer,
            "duration": duration,
            "is_long": is_long,
            "skipped": False,
            "snoozed": False,
        }

        def _on_tick() -> None:
            if not self._break_state:
                return
            self._break_state["remaining"] -= 1
            if self._break_state["remaining"] <= 0:
                self._end_break(completed=True)

        countdown_timer.timeout.connect(_on_tick)
        countdown_timer.start()

        primary.skipped.connect(lambda: self._end_break(completed=False, skipped=True))
        primary.snoozed.connect(lambda: self._end_break(completed=False, snoozed=True))
        primary.finished.connect(lambda: self._end_break(completed=True))

        play_async(sound_path(self._settings.sound_set, "start"), self._settings.sound_volume)
        self._scheduler.suspend()

    def _end_break(self, *, completed: bool = False, skipped: bool = False, snoozed: bool = False) -> None:
        if self._break_state is None:
            return
        state = self._break_state
        self._break_state = None
        state["timer"].stop()
        self._overlay.close()
        self._scheduler.unsuspend()

        if completed:
            play_async(sound_path(self._settings.sound_set, "end"), self._settings.sound_volume)
        self._stats.record_break(
            duration_s=state["duration"],
            completed=completed,
            skipped=skipped,
            snoozed=snoozed,
            long_break=state["is_long"],
        )
        if snoozed:
            self._scheduler.snooze(self._settings.snooze_seconds)
        else:
            self._scheduler.reset_after_break(completed=completed)

    def _fire_blink(self) -> None:
        self._notify("Blink reminder", "Blink slowly a few times — let your eyes refresh.")

    def _fire_posture(self) -> None:
        self._notify("Posture check", "Sit tall, relax shoulders, screen at eye level.")

    def _notify(self, title: str, body: str) -> None:
        if not self._settings.notifications_enabled:
            return
        cmd = shutil.which("notify-send")
        if not cmd:
            return
        icon_path = asset_dir() / "icon" / "icon.png"
        args = [cmd, "-i", str(icon_path), "-a", APP_NAME, "-t", "5000", title, body]
        try:
            subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except OSError:
            pass

    def _record_screen_time(self) -> None:
        if self._scheduler.is_paused():
            return
        if self._idle.idle_seconds() >= max(5, self._settings.idle_pause_seconds):
            return
        self._stats.add_screen_time(60)

    def _on_tray_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self._open_settings()

    def _about(self) -> None:
        QMessageBox.information(
            None,
            "About LookAway for Linux",
            f"{APP_NAME}\n\nA Linux-native reimplementation of the macOS app LookAway.\n"
            f"Config: {CONFIG_DIR}\n",
        )

    def _update_autostart(self, enable: bool) -> None:
        autostart_dir = Path.home() / ".config" / "autostart"
        autostart_dir.mkdir(parents=True, exist_ok=True)
        file = autostart_dir / f"{APP_ID}.desktop"
        if enable:
            launcher = Path.home() / "LookAwayLinux" / "bin" / "lookaway"
            file.write_text(
                "[Desktop Entry]\n"
                f"Name={APP_NAME}\n"
                "Comment=Break reminder\n"
                f"Exec={launcher}\n"
                f"Icon={asset_dir() / 'icon' / 'icon.png'}\n"
                "Type=Application\n"
                "Categories=Utility;\n"
                "X-GNOME-Autostart-enabled=true\n"
            )
        else:
            try:
                file.unlink()
            except FileNotFoundError:
                pass

    def _quit(self) -> None:
        self._scheduler.stop()
        self._overlay.close()
        self._qapp.quit()


def main() -> int:
    if not os.environ.get("DISPLAY") and not os.environ.get("WAYLAND_DISPLAY"):
        print("LookAway requires a graphical session (no DISPLAY/WAYLAND_DISPLAY).", file=sys.stderr)
        return 2

    qInstallMessageHandler(_qt_message_filter)
    qapp = QApplication(sys.argv)
    qapp.setDesktopFileName(APP_ID)
    qapp.setApplicationDisplayName(APP_NAME)

    if not QSystemTrayIcon.isSystemTrayAvailable():
        print("System tray not available on this desktop.", file=sys.stderr)
        return 3

    app = LookAwayApp(qapp)
    signal.signal(signal.SIGINT, lambda *_: app._quit())
    signal.signal(signal.SIGTERM, lambda *_: app._quit())
    sigtimer = QTimer()
    sigtimer.start(500)
    sigtimer.timeout.connect(lambda: None)

    return qapp.exec()


if __name__ == "__main__":
    raise SystemExit(main())
