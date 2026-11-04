"""Persistent, offline focus timer and hydration tracking for Mobius.

No Qt, accounts or network. Time values are injected to enable deterministic tests.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import datetime, date
from pathlib import Path
from time import time


def data_file() -> Path:
    return Path(os.environ.get("MOBIUS_DATA_DIR", str(Path.home() / ".mobius"))) / "wellness.json"


@dataclass
class FocusTimer:
    work_minutes: int = 25
    break_minutes: int = 5
    mode: str = "focus"
    deadline: float | None = None
    remaining_at_pause: int = 1500
    completed_sessions: int = 0

    def duration(self) -> int:
        return 60 * (self.work_minutes if self.mode == "focus" else self.break_minutes)

    def start(self, now: float | None = None) -> None:
        now = time() if now is None else now
        if self.deadline is None:
            self.deadline = now + max(1, self.remaining_at_pause)

    def pause(self, now: float | None = None) -> None:
        if self.deadline is not None:
            self.remaining_at_pause = self.remaining(now)
            self.deadline = None

    def reset(self) -> None:
        self.deadline = None
        self.remaining_at_pause = self.duration()

    def remaining(self, now: float | None = None) -> int:
        now = time() if now is None else now
        return max(0, int(self.deadline - now + .999)) if self.deadline is not None else self.remaining_at_pause

    def tick(self, now: float | None = None) -> bool:
        """If a session expires, move to the other mode; return True once."""
        if self.deadline is None or self.remaining(now) > 0:
            return False
        if self.mode == "focus":
            self.completed_sessions += 1
            self.mode = "break"
        else:
            self.mode = "focus"
        self.reset()
        return True


@dataclass
class Hydration:
    bottle_ml: int = 250
    goal_ml: int = 2000
    interval_minutes: int = 60
    active_start_hour: int = 9
    active_end_hour: int = 20
    day: str = field(default_factory=lambda: date.today().isoformat())
    entries: list[dict] = field(default_factory=list)
    last_reminded_at: float = 0

    def ensure_today(self, now: datetime | None = None) -> None:
        now = now or datetime.now()
        today = now.date().isoformat()
        if today != self.day:
            self.day = today
            self.entries = []
            self.last_reminded_at = 0

    def consumed(self) -> int:
        return sum(max(0, int(row.get("ml", 0))) for row in self.entries)

    def add(self, amount: int | None = None, now: datetime | None = None) -> int:
        now = now or datetime.now()
        self.ensure_today(now)
        ml = self.bottle_ml if amount is None else int(amount)
        if not 1 <= ml <= 5000:
            raise ValueError("Ukuran air harus 1–5000 ml")
        self.entries.append({"at": now.isoformat(timespec="seconds"), "ml": ml})
        return self.consumed()

    def hourly_chart(self) -> list[int]:
        result = [0] * 24
        for row in self.entries:
            try:
                hour = datetime.fromisoformat(row["at"]).hour
                result[hour] += int(row["ml"])
            except (ValueError, KeyError, TypeError):
                continue
        return result

    def should_remind(self, now: datetime | None = None) -> bool:
        now = now or datetime.now()
        self.ensure_today(now)
        if not self.active_start_hour <= now.hour < self.active_end_hour:
            return False
        if self.consumed() >= self.goal_ml:
            return False
        recent_drink = max((datetime.fromisoformat(r["at"]).timestamp()
                            for r in self.entries if "at" in r), default=0.0)
        gap = self.interval_minutes * 60
        return now.timestamp() - max(recent_drink, self.last_reminded_at) >= gap

    def mark_reminded(self, now: datetime | None = None) -> None:
        self.last_reminded_at = (now or datetime.now()).timestamp()


class WellnessStore:
    def __init__(self, path: Path | None = None):
        self.path = path or data_file()
        self.focus = FocusTimer()
        self.water = Hydration()
        self.load()

    def load(self) -> None:
        if not self.path.exists():
            return
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            w = raw.get("water", {})
            for key in ("bottle_ml", "goal_ml", "interval_minutes", "active_start_hour",
                        "active_end_hour", "day", "entries", "last_reminded_at"):
                if key in w:
                    setattr(self.water, key, w[key])
            focus = raw.get("focus", {})
            for key in ("work_minutes", "break_minutes", "completed_sessions"):
                if key in focus:
                    setattr(self.focus, key, focus[key])
            # Restarting never accidentally resumes a shutdown-sized session.
            self.focus.reset()
            self.water.ensure_today()
        except (ValueError, TypeError, OSError, KeyError, AttributeError):
            # Corrupt configuration should not prevent app launch.
            self.focus = FocusTimer()
            self.water = Hydration()

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "water": {k: getattr(self.water, k) for k in (
                "bottle_ml", "goal_ml", "interval_minutes", "active_start_hour",
                "active_end_hour", "day", "entries", "last_reminded_at")},
            "focus": {k: getattr(self.focus, k) for k in (
                "work_minutes", "break_minutes", "completed_sessions")},
        }
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(self.path)
