from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path
from typing import Any

CONFIG_DIR = Path(os.environ.get("XDG_CONFIG_HOME", str(Path.home() / ".config"))) / "lookaway-linux"
CONFIG_FILE = CONFIG_DIR / "config.json"
DATA_DIR = Path(os.environ.get("XDG_DATA_HOME", str(Path.home() / ".local" / "share"))) / "lookaway-linux"
STATS_DB = DATA_DIR / "stats.db"


@dataclass
class Settings:
    work_minutes: int = 20
    break_seconds: int = 20
    long_break_every: int = 4
    long_break_seconds: int = 300
    enforce_break: str = "gentle"
    idle_pause_seconds: int = 60
    sound_set: str = "bell"
    sound_volume: int = 80
    blink_reminder_enabled: bool = True
    blink_reminder_minutes: int = 10
    posture_reminder_enabled: bool = True
    posture_reminder_minutes: int = 30
    notifications_enabled: bool = True
    autostart: bool = False
    show_countdown: bool = True
    snooze_seconds: int = 300
    snooze_limit_per_day: int = 4
    countdown_bubble_enabled: bool = True

    @classmethod
    def load(cls) -> "Settings":
        if CONFIG_FILE.exists():
            try:
                raw: dict[str, Any] = json.loads(CONFIG_FILE.read_text())
            except (OSError, json.JSONDecodeError):
                raw = {}
        else:
            raw = {}
        valid = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in raw.items() if k in valid})

    def save(self) -> None:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        CONFIG_FILE.write_text(json.dumps(asdict(self), indent=2))


ENFORCE_LEVELS = {
    "gentle": "Show overlay; allow skip and snooze freely.",
    "balanced": "Show overlay; require typing 'ok' to skip.",
    "strict": "Lock the screen; only snooze allowed (limited per day).",
}

SOUND_SETS = ["bell", "bubbles", "flute", "harp", "original", "piano", "twinkle", "whoosh", "v2"]


def asset_dir() -> Path:
    return Path(__file__).resolve().parent.parent / "assets"


def sound_path(set_name: str, kind: str) -> Path:
    name_map = {"v2": ("v2-break-start", "v2-break-end")}
    if set_name in name_map:
        start, end = name_map[set_name]
        fname = (start if kind == "start" else end) + ".m4a"
    else:
        fname = f"{set_name}-{kind}.mp3"
    return asset_dir() / "sounds" / fname
