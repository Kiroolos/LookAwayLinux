# LookAway for Linux

A Kali/Linux-native re-implementation of the macOS app **LookAway**.

## Why this exists

The official LookAway is a closed-source SwiftUI/AppKit Mach-O binary that uses
macOS-only frameworks (AppKit, Metal, AppIntents, EventKit, AppleScript, Sparkle).
There is no path to "convert" it to Linux: we don't have the source code, and
SwiftUI / AppKit don't exist on Linux. Darling will not run a modern SwiftUI app
either.

This project takes the audio assets, fonts and icon extracted from the original
`.app` bundle and pairs them with a from-scratch PyQt6 implementation of the
core features.

## Features

- 20-20-20-style break reminders with full-screen overlay
- Long breaks every N short breaks
- Idle detection (X11 ScreenSaver extension via `libXss`)
- Blink and posture micro-reminders via `notify-send`
- Three enforcement modes: Gentle / Balanced / Strict
- Daily snooze limit
- Multi-monitor overlay
- Per-day stats persisted in SQLite (`~/.local/share/lookaway-linux/stats.db`)
- Sound preview in settings
- KDE / GNOME autostart toggle

## Run

```
~/LookAwayLinux/bin/lookaway
```

The app lives in the system tray. Left-click or right-click the tray icon to
open settings, take a break now, pause, or quit.

## Install desktop launcher

```
cp ~/LookAwayLinux/lookaway-linux.desktop ~/.local/share/applications/
update-desktop-database ~/.local/share/applications/ 2>/dev/null || true
```

## Dependencies (already installed on Kali 2025.4)

- Python 3 + PyQt6
- `ffplay` (from `ffmpeg`) or `paplay` / `mpg123` for sound playback
- `libnotify` / `notify-send` for micro-reminders
- `libXss` / `libX11` for idle detection (X11 only)

## Files

```
LookAwayLinux/
├── assets/
│   ├── fonts/   Original LookAway fonts
│   ├── icon/    PNG icons extracted from AppIcon.icns
│   ├── sounds/  Original LookAway sounds
│   └── video/   Marketing videos (not used at runtime)
├── bin/lookaway
├── lookaway-linux.desktop
├── README.md
└── src/
    ├── audio.py
    ├── config.py
    ├── idle.py
    ├── main.py
    ├── overlay.py
    ├── scheduler.py
    ├── settings_dialog.py
    └── stats.py
```

## Wayland note

Idle detection uses the X11 ScreenSaver extension. KDE Plasma on Wayland exposes
an X11 fallback through XWayland; pure Wayland sessions without XWayland will
report idle = 0 and won't pause the timer when you step away.

## Support

If this saved your eyes a few hours of strain, a small tip is appreciated 🙏

<p align="left">
  <a href="https://paypal.me/kiroolosss">
    <img src="https://img.shields.io/badge/PayPal-Donate-00457C?style=for-the-badge&logo=paypal&logoColor=white" alt="Donate via PayPal" />
  </a>
</p>

→ [paypal.me/kiroolosss](https://paypal.me/kiroolosss)

