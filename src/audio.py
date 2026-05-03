from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

_PLAYERS = [
    ("ffplay", ["-autoexit", "-nodisp", "-loglevel", "quiet", "-volume", "{vol}", "{path}"]),
    ("paplay", ["--volume={pavol}", "{path}"]),
    ("mpg123", ["-q", "-f", "{mpg_vol}", "{path}"]),
    ("aplay", ["-q", "{path}"]),
]


def _resolve_player() -> tuple[str, list[str]] | None:
    for name, template in _PLAYERS:
        if shutil.which(name):
            return name, template
    return None


_PLAYER = _resolve_player()


def play_async(path: str | Path, volume_pct: int = 80) -> subprocess.Popen | None:
    if _PLAYER is None:
        return None
    p = Path(path)
    if not p.exists():
        return None
    name, template = _PLAYER
    volume_pct = max(0, min(100, int(volume_pct)))
    pavol = int(volume_pct * 65536 / 100)
    mpg_vol = int(volume_pct * 32768 / 100)
    args = [name] + [
        a.format(vol=volume_pct, pavol=pavol, mpg_vol=mpg_vol, path=str(p)) for a in template
    ]
    try:
        return subprocess.Popen(
            args,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
            start_new_session=True,
        )
    except OSError:
        return None


def player_name() -> str:
    return _PLAYER[0] if _PLAYER else "none"
