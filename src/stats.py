from __future__ import annotations

import sqlite3
from datetime import date, datetime
from pathlib import Path

from .config import DATA_DIR, STATS_DB


SCHEMA = """
CREATE TABLE IF NOT EXISTS breaks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at TEXT NOT NULL,
    duration_s INTEGER NOT NULL,
    completed INTEGER NOT NULL DEFAULT 0,
    skipped INTEGER NOT NULL DEFAULT 0,
    snoozed INTEGER NOT NULL DEFAULT 0,
    long_break INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS screen_time (
    day TEXT PRIMARY KEY,
    seconds INTEGER NOT NULL DEFAULT 0
);
"""


class Stats:
    def __init__(self, db_path: Path = STATS_DB) -> None:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        self._db_path = db_path
        self._conn = sqlite3.connect(str(db_path))
        self._conn.executescript(SCHEMA)
        self._conn.commit()

    def record_break(self, duration_s: int, *, completed: bool, skipped: bool, snoozed: bool, long_break: bool) -> None:
        self._conn.execute(
            "INSERT INTO breaks(started_at, duration_s, completed, skipped, snoozed, long_break) VALUES (?, ?, ?, ?, ?, ?)",
            (datetime.now().isoformat(timespec="seconds"), duration_s, int(completed), int(skipped), int(snoozed), int(long_break)),
        )
        self._conn.commit()

    def add_screen_time(self, seconds: int) -> None:
        if seconds <= 0:
            return
        today = date.today().isoformat()
        self._conn.execute(
            "INSERT INTO screen_time(day, seconds) VALUES (?, ?) "
            "ON CONFLICT(day) DO UPDATE SET seconds = seconds + excluded.seconds",
            (today, seconds),
        )
        self._conn.commit()

    def snoozes_today(self) -> int:
        today = date.today().isoformat()
        cur = self._conn.execute(
            "SELECT COUNT(*) FROM breaks WHERE date(started_at) = ? AND snoozed = 1",
            (today,),
        )
        return int(cur.fetchone()[0])

    def today_summary(self) -> dict[str, int]:
        today = date.today().isoformat()
        cur = self._conn.execute(
            "SELECT "
            "  SUM(CASE WHEN completed=1 THEN 1 ELSE 0 END), "
            "  SUM(CASE WHEN skipped=1 THEN 1 ELSE 0 END), "
            "  SUM(CASE WHEN snoozed=1 THEN 1 ELSE 0 END) "
            "FROM breaks WHERE date(started_at) = ?",
            (today,),
        )
        completed, skipped, snoozed = cur.fetchone()
        cur = self._conn.execute(
            "SELECT seconds FROM screen_time WHERE day = ?", (today,)
        )
        row = cur.fetchone()
        screen = int(row[0]) if row else 0
        return {
            "completed": int(completed or 0),
            "skipped": int(skipped or 0),
            "snoozed": int(snoozed or 0),
            "screen_seconds": screen,
        }

    def history(self, days: int = 7) -> list[tuple[str, int, int, int]]:
        cur = self._conn.execute(
            "SELECT date(started_at) AS day, "
            "       SUM(CASE WHEN completed=1 THEN 1 ELSE 0 END) AS done, "
            "       SUM(CASE WHEN skipped=1 THEN 1 ELSE 0 END) AS skipped, "
            "       SUM(CASE WHEN snoozed=1 THEN 1 ELSE 0 END) AS snoozed "
            "FROM breaks GROUP BY day ORDER BY day DESC LIMIT ?",
            (days,),
        )
        return [(r[0], int(r[1] or 0), int(r[2] or 0), int(r[3] or 0)) for r in cur.fetchall()]
