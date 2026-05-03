"""3-second overlay smoketest. Proves the break path renders + auto-closes."""
from __future__ import annotations

import sys

from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QApplication

from .audio import play_async
from .config import Settings, sound_path
from .overlay import BreakRequest, OverlayController


def main() -> int:
    app = QApplication(sys.argv)
    settings = Settings()
    controller = OverlayController()
    duration = 3
    state = {"remaining": duration}
    request = BreakRequest(
        duration_s=duration,
        long_break=False,
        enforce="gentle",
        show_countdown=True,
        can_snooze=True,
    )
    primary, _ = controller.show(request, lambda: state["remaining"])
    play_async(sound_path(settings.sound_set, "start"), 50)

    def tick():
        state["remaining"] -= 1
        if state["remaining"] <= 0:
            ticker.stop()
            controller.close()
            QTimer.singleShot(200, app.quit)

    ticker = QTimer()
    ticker.setInterval(1000)
    ticker.timeout.connect(tick)
    ticker.start()

    primary.skipped.connect(lambda: app.quit())
    primary.snoozed.connect(lambda: app.quit())
    primary.finished.connect(lambda: app.quit())

    QTimer.singleShot((duration + 2) * 1000, app.quit)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
