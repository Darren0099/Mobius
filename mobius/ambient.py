"""Compact island glance scheduling and Windows battery state.

This module has no Qt imports. It never reads microphone or sends any data.
Each non-eye glance is capped at 10 seconds before returning to the avatar.
"""
from __future__ import annotations

import ctypes
import sys
from dataclasses import dataclass
from datetime import datetime
from typing import Iterable


@dataclass(frozen=True)
class PowerState:
    percent: int | None
    plugged: bool | None

    @property
    def label(self) -> str:
        if self.percent is None:
            return "Battery unavailable"
        if self.plugged is True:
            return f"⚡ {self.percent}% · Charging"
        if self.plugged is False:
            return f"▰ {self.percent}% · On battery"
        return f"▰ {self.percent}%"

    @property
    def accent(self) -> str:
        if self.percent is not None and self.percent <= 15 and not self.plugged:
            return "#FF6C63"
        return "#8BF570" if self.plugged else "#E6EAF0"


def read_windows_power() -> PowerState:
    if sys.platform != "win32":
        return PowerState(None, None)

    class SystemPowerStatus(ctypes.Structure):
        _fields_ = [
            ("ACLineStatus", ctypes.c_ubyte),
            ("BatteryFlag", ctypes.c_ubyte),
            ("BatteryLifePercent", ctypes.c_ubyte),
            ("SystemStatusFlag", ctypes.c_ubyte),
            ("BatteryLifeTime", ctypes.c_ulong),
            ("BatteryFullLifeTime", ctypes.c_ulong),
        ]

    try:
        result = SystemPowerStatus()
        if not ctypes.windll.kernel32.GetSystemPowerStatus(ctypes.byref(result)):
            return PowerState(None, None)
        percent = int(result.BatteryLifePercent)
        if percent == 255:
            percent = None
        return PowerState(percent, {0: False, 1: True}.get(int(result.ACLineStatus)))
    except (OSError, AttributeError, TypeError, ValueError):
        return PowerState(None, None)


class GlanceController:
    """Periodic glance cycle with priority for battery/charger state changes.

    Eyes are shown between glances, and every glance lasts exactly the
    configured window at most, regardless of frequent GUI/media polling.
    """

    def __init__(self, *, interval_seconds: float = 38,
                 duration_seconds: float = 10, start_now: float = 0):
        self.interval = float(interval_seconds)
        self.duration = float(duration_seconds)
        self.kind = "eyes"
        self.message = ""
        self.accent = "#E6EAF0"
        self.until = 0.0
        self.next_at = start_now + self.interval
        self._round_robin = 0

    def show(self, kind: str, message: str, now: float, accent: str = "#E6EAF0"):
        if not message:
            return
        self.kind = kind
        self.message = message
        self.accent = accent
        self.until = now + self.duration
        self.next_at = self.until + self.interval

    def tick(self, now: float, options: Iterable[tuple[str, str, str]]) -> str:
        if self.kind != "eyes":
            if now < self.until:
                return self.kind
            self.kind = "eyes"
            self.message = ""
            # Do not immediately start another glance on the same tick.
            self.next_at = max(self.next_at, now + self.interval)
            return self.kind

        if now < self.next_at:
            return self.kind
        choices = [x for x in options if x[1]]
        if not choices:
            self.next_at = now + self.interval
            return self.kind
        item = choices[self._round_robin % len(choices)]
        self._round_robin += 1
        self.show(item[0], item[1], now, item[2])
        return self.kind


def clock_label(now: datetime | None = None) -> str:
    now = now or datetime.now()
    return now.strftime("%H:%M  ·  %d %b")
