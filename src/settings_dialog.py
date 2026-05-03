from __future__ import annotations

from datetime import timedelta

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont, QIcon
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QSpinBox,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from .audio import play_async, player_name
from .config import ENFORCE_LEVELS, SOUND_SETS, Settings, sound_path
from .stats import Stats


class SettingsDialog(QDialog):
    settings_applied = pyqtSignal(Settings)

    def __init__(self, settings: Settings, stats: Stats, parent: QWidget | None = None, app_icon: QIcon | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("LookAway · Settings")
        if app_icon is not None:
            self.setWindowIcon(app_icon)
        self.resize(620, 580)
        self._settings = Settings(**vars(settings))
        self._stats = stats

        layout = QVBoxLayout(self)
        tabs = QTabWidget()
        layout.addWidget(tabs, 1)

        tabs.addTab(self._build_general_tab(), "General")
        tabs.addTab(self._build_reminders_tab(), "Reminders")
        tabs.addTab(self._build_sounds_tab(), "Sounds")
        tabs.addTab(self._build_stats_tab(), "Stats")
        tabs.addTab(self._build_about_tab(), "About")

        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Apply | QDialogButtonBox.StandardButton.Cancel)
        bb.button(QDialogButtonBox.StandardButton.Ok).clicked.connect(self._apply_and_close)
        bb.button(QDialogButtonBox.StandardButton.Apply).clicked.connect(self._apply)
        bb.button(QDialogButtonBox.StandardButton.Cancel).clicked.connect(self.reject)
        layout.addWidget(bb)

    def _build_general_tab(self) -> QWidget:
        w = QWidget()
        form = QFormLayout(w)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self._work = QSpinBox()
        self._work.setRange(1, 240)
        self._work.setSuffix(" min")
        self._work.setValue(self._settings.work_minutes)
        form.addRow("Work interval", self._work)

        self._breakd = QSpinBox()
        self._breakd.setRange(5, 600)
        self._breakd.setSuffix(" sec")
        self._breakd.setValue(self._settings.break_seconds)
        form.addRow("Short-break duration", self._breakd)

        self._longn = QSpinBox()
        self._longn.setRange(0, 24)
        self._longn.setValue(self._settings.long_break_every)
        self._longn.setSpecialValueText("disabled")
        form.addRow("Long break every (N breaks)", self._longn)

        self._longd = QSpinBox()
        self._longd.setRange(30, 3600)
        self._longd.setSuffix(" sec")
        self._longd.setValue(self._settings.long_break_seconds)
        form.addRow("Long-break duration", self._longd)

        self._enforce = QComboBox()
        for k in ENFORCE_LEVELS:
            self._enforce.addItem(k.title(), k)
        idx = max(0, self._enforce.findData(self._settings.enforce_break))
        self._enforce.setCurrentIndex(idx)
        form.addRow("Enforcement", self._enforce)
        self._enforce_desc = QLabel(ENFORCE_LEVELS[self._settings.enforce_break])
        self._enforce_desc.setWordWrap(True)
        self._enforce_desc.setStyleSheet("color: #888;")
        self._enforce.currentIndexChanged.connect(
            lambda _: self._enforce_desc.setText(ENFORCE_LEVELS[self._enforce.currentData()])
        )
        form.addRow("", self._enforce_desc)

        self._idle = QSpinBox()
        self._idle.setRange(15, 1800)
        self._idle.setSuffix(" sec")
        self._idle.setValue(self._settings.idle_pause_seconds)
        form.addRow("Pause when idle for", self._idle)

        self._countdown = QCheckBox("Show countdown timer during break")
        self._countdown.setChecked(self._settings.show_countdown)
        form.addRow("", self._countdown)

        self._bubble = QCheckBox("Show floating countdown bubble (always-on-top)")
        self._bubble.setChecked(self._settings.countdown_bubble_enabled)
        form.addRow("", self._bubble)

        self._snooze_s = QSpinBox()
        self._snooze_s.setRange(30, 3600)
        self._snooze_s.setSuffix(" sec")
        self._snooze_s.setValue(self._settings.snooze_seconds)
        form.addRow("Snooze length", self._snooze_s)

        self._snooze_lim = QSpinBox()
        self._snooze_lim.setRange(0, 100)
        self._snooze_lim.setValue(self._settings.snooze_limit_per_day)
        self._snooze_lim.setSpecialValueText("unlimited")
        form.addRow("Daily snooze limit", self._snooze_lim)

        return w

    def _build_reminders_tab(self) -> QWidget:
        w = QWidget()
        outer = QVBoxLayout(w)

        notif_box = QGroupBox("Notifications")
        nl = QFormLayout(notif_box)
        self._notif = QCheckBox("Enable system notifications (notify-send)")
        self._notif.setChecked(self._settings.notifications_enabled)
        nl.addRow("", self._notif)
        outer.addWidget(notif_box)

        blink_box = QGroupBox("Blink reminder")
        bl = QFormLayout(blink_box)
        self._blink_en = QCheckBox("Enabled")
        self._blink_en.setChecked(self._settings.blink_reminder_enabled)
        bl.addRow("", self._blink_en)
        self._blink_min = QSpinBox()
        self._blink_min.setRange(1, 240)
        self._blink_min.setSuffix(" min")
        self._blink_min.setValue(self._settings.blink_reminder_minutes)
        bl.addRow("Frequency", self._blink_min)
        outer.addWidget(blink_box)

        post_box = QGroupBox("Posture reminder")
        pl = QFormLayout(post_box)
        self._post_en = QCheckBox("Enabled")
        self._post_en.setChecked(self._settings.posture_reminder_enabled)
        pl.addRow("", self._post_en)
        self._post_min = QSpinBox()
        self._post_min.setRange(1, 240)
        self._post_min.setSuffix(" min")
        self._post_min.setValue(self._settings.posture_reminder_minutes)
        pl.addRow("Frequency", self._post_min)
        outer.addWidget(post_box)

        autostart_box = QGroupBox("Startup")
        al = QFormLayout(autostart_box)
        self._autostart = QCheckBox("Start LookAway when I log in (KDE/GNOME autostart)")
        self._autostart.setChecked(self._settings.autostart)
        al.addRow("", self._autostart)
        outer.addWidget(autostart_box)

        outer.addStretch(1)
        return w

    def _build_sounds_tab(self) -> QWidget:
        w = QWidget()
        outer = QVBoxLayout(w)
        form = QFormLayout()

        self._sound = QComboBox()
        for s in SOUND_SETS:
            self._sound.addItem(s.capitalize(), s)
        idx = max(0, self._sound.findData(self._settings.sound_set))
        self._sound.setCurrentIndex(idx)
        form.addRow("Sound set", self._sound)

        vol_row = QHBoxLayout()
        self._vol = QSlider(Qt.Orientation.Horizontal)
        self._vol.setRange(0, 100)
        self._vol.setValue(self._settings.sound_volume)
        self._vol_label = QLabel(f"{self._settings.sound_volume}%")
        self._vol.valueChanged.connect(lambda v: self._vol_label.setText(f"{v}%"))
        vol_row.addWidget(self._vol, 1)
        vol_row.addWidget(self._vol_label)
        form.addRow("Volume", vol_row)

        outer.addLayout(form)

        preview_row = QHBoxLayout()
        start_btn = QPushButton("Preview start")
        start_btn.clicked.connect(lambda: self._preview("start"))
        end_btn = QPushButton("Preview end")
        end_btn.clicked.connect(lambda: self._preview("end"))
        preview_row.addStretch(1)
        preview_row.addWidget(start_btn)
        preview_row.addWidget(end_btn)
        outer.addLayout(preview_row)

        info = QLabel(f"Audio backend: {player_name()}")
        info.setStyleSheet("color: #888;")
        outer.addWidget(info)
        outer.addStretch(1)
        return w

    def _build_stats_tab(self) -> QWidget:
        w = QWidget()
        outer = QVBoxLayout(w)

        today = self._stats.today_summary()
        screen = str(timedelta(seconds=today["screen_seconds"]))
        head = QLabel(
            f"<b>Today</b> &nbsp; ✔ {today['completed']} completed &nbsp; "
            f"⏭ {today['skipped']} skipped &nbsp; ⏰ {today['snoozed']} snoozed &nbsp; "
            f"🖥 {screen} screen time"
        )
        head.setTextFormat(Qt.TextFormat.RichText)
        outer.addWidget(head)

        history = self._stats.history(14)
        table = QTableWidget(len(history), 4)
        table.setHorizontalHeaderLabels(["Day", "Completed", "Skipped", "Snoozed"])
        table.verticalHeader().setVisible(False)
        for r, row in enumerate(history):
            for c, val in enumerate(row):
                item = QTableWidgetItem(str(val))
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                table.setItem(r, c, item)
        table.resizeColumnsToContents()
        outer.addWidget(table, 1)
        return w

    def _build_about_tab(self) -> QWidget:
        w = QWidget()
        outer = QVBoxLayout(w)
        title = QLabel("LookAway for Linux")
        f = QFont()
        f.setPointSize(16)
        f.setBold(True)
        title.setFont(f)
        outer.addWidget(title)
        body = QLabel(
            "A Kali/Linux-native re-implementation of the macOS app LookAway.\n\n"
            "Reuses the original sounds, fonts and icon (extracted from the .app).\n\n"
            "Features:\n"
            "  • 20-20-20-style break reminders with full-screen overlay\n"
            "  • Idle detection (X11 ScreenSaver extension)\n"
            "  • Blink and posture micro-reminders via notify-send\n"
            "  • Long breaks every N breaks\n"
            "  • Gentle / Balanced / Strict enforcement\n"
            "  • Daily snooze limit\n"
            "  • Stats persisted in SQLite\n\n"
            "This is not the official LookAway app, which is closed-source and macOS-only.\n"
            "It cannot be re-linked for Linux. This is an independent implementation."
        )
        body.setWordWrap(True)
        outer.addWidget(body, 1)
        return w

    def _preview(self, kind: str) -> None:
        path = sound_path(self._sound.currentData(), kind)
        play_async(path, self._vol.value())

    def _collect(self) -> Settings:
        return Settings(
            work_minutes=self._work.value(),
            break_seconds=self._breakd.value(),
            long_break_every=self._longn.value(),
            long_break_seconds=self._longd.value(),
            enforce_break=self._enforce.currentData(),
            idle_pause_seconds=self._idle.value(),
            sound_set=self._sound.currentData(),
            sound_volume=self._vol.value(),
            blink_reminder_enabled=self._blink_en.isChecked(),
            blink_reminder_minutes=self._blink_min.value(),
            posture_reminder_enabled=self._post_en.isChecked(),
            posture_reminder_minutes=self._post_min.value(),
            notifications_enabled=self._notif.isChecked(),
            autostart=self._autostart.isChecked(),
            show_countdown=self._countdown.isChecked(),
            snooze_seconds=self._snooze_s.value(),
            snooze_limit_per_day=self._snooze_lim.value(),
            countdown_bubble_enabled=self._bubble.isChecked(),
        )

    def _apply(self) -> None:
        self._settings = self._collect()
        self._settings.save()
        self.settings_applied.emit(self._settings)

    def _apply_and_close(self) -> None:
        self._apply()
        self.accept()
