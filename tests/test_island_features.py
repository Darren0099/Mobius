"""Unit and Qt smoke tests for Mobius's new island features."""
import os
from datetime import datetime
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from mobius.lyrics import parse_lrc, active_line
from mobius.wellness import FocusTimer, Hydration, WellnessStore


def test_lrc_multiple_timestamps_and_active_lines():
    lines = parse_lrc("[00:01.20][00:02.50] First line\n[00:05.30] Second line")
    assert lines == [(1.2, "First line"), (2.5, "First line"), (5.3, "Second line")]
    assert active_line(lines, 0.1) == -1
    assert active_line(lines, 1.3) == 0
    assert active_line(lines, 5.5) == 2


def test_lrc_does_not_require_network_or_song_lyrics():
    assert parse_lrc("[ar:Some Artist]\n[ti:A title]") == []
    assert parse_lrc("") == []


def test_focus_start_pause_resume_transition():
    timer = FocusTimer(work_minutes=1, break_minutes=1, remaining_at_pause=60)
    timer.start(now=100)
    assert timer.remaining(now=120) == 40
    timer.pause(now=120)
    assert timer.remaining(now=500) == 40
    timer.start(now=600)
    assert timer.remaining(now=630) == 10
    assert not timer.tick(now=630)
    assert timer.tick(now=640)
    assert timer.mode == 'break'
    assert timer.completed_sessions == 1
    assert timer.remaining() == 60


def test_water_tracking_and_daily_reset(tmp_path):
    path = tmp_path / "state.json"
    store = WellnessStore(path)
    now = datetime(2026, 11, 4, 10, 5)
    assert store.water.add(250, now) == 250
    assert store.water.add(100, now) == 350
    assert store.water.hourly_chart()[10] == 350
    store.save()
    another = WellnessStore(path)
    # The loader resets stale dates to the actual current date.
    assert another.water.goal_ml == 2000
    assert another.water.bottle_ml == 250
    another.water.ensure_today(datetime(2026, 11, 5, 10, 5))
    assert another.water.consumed() == 0


def test_water_reminder_respects_active_hours_and_goal():
    w = Hydration(day='2026-11-04', goal_ml=500)
    assert not w.should_remind(datetime(2026, 11, 4, 8, 30))
    assert w.should_remind(datetime(2026, 11, 4, 10, 0))
    w.mark_reminded(datetime(2026, 11, 4, 10, 0))
    assert not w.should_remind(datetime(2026, 11, 4, 10, 25))
    w.add(500, datetime(2026, 11, 4, 10, 30))
    assert not w.should_remind(datetime(2026, 11, 4, 13, 0))


def test_music_bridge_duration_helpers():
    from datetime import timedelta
    from mobius.media_bridge import _as_seconds, _status
    assert _as_seconds(timedelta(seconds=12.5)) == 12.5
    assert _as_seconds(None) == 0
    assert _status("PLAYING") == "playing"


def test_quick_deck_qt_widget_creation():
    from PySide6.QtWidgets import QApplication
    from mobius.quick_deck import QuickDeck
    app = QApplication.instance() or QApplication([])
    deck = QuickDeck()
    assert len(deck.nav) == 4
    assert deck.pages.isHidden()
    deck.toggle_page(2)
    assert not deck.pages.isHidden()
    deck.toggle_page(2)
    assert deck.pages.isHidden()
    deck.stop()
    deck.deleteLater()
