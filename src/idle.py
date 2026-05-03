from __future__ import annotations

import ctypes
from ctypes import POINTER, Structure, c_int, c_ulong, c_void_p


class _XScreenSaverInfo(Structure):
    _fields_ = [
        ("window", c_ulong),
        ("state", c_int),
        ("kind", c_int),
        ("til_or_since", c_ulong),
        ("idle", c_ulong),
        ("event_mask", c_ulong),
    ]


class IdleMonitor:
    def __init__(self) -> None:
        self._x11 = ctypes.CDLL("libX11.so.6")
        self._xss = ctypes.CDLL("libXss.so.1")
        self._x11.XOpenDisplay.restype = c_void_p
        self._x11.XOpenDisplay.argtypes = [ctypes.c_char_p]
        self._x11.XDefaultRootWindow.restype = c_ulong
        self._x11.XDefaultRootWindow.argtypes = [c_void_p]
        self._xss.XScreenSaverAllocInfo.restype = POINTER(_XScreenSaverInfo)
        self._xss.XScreenSaverQueryInfo.argtypes = [c_void_p, c_ulong, POINTER(_XScreenSaverInfo)]
        self._xss.XScreenSaverQueryInfo.restype = c_int
        self._dpy = self._x11.XOpenDisplay(None)
        self._info = self._xss.XScreenSaverAllocInfo()
        self._available = bool(self._dpy)

    def idle_seconds(self) -> int:
        if not self._available:
            return 0
        root = self._x11.XDefaultRootWindow(self._dpy)
        if self._xss.XScreenSaverQueryInfo(self._dpy, root, self._info) == 0:
            return 0
        return int(self._info.contents.idle // 1000)
