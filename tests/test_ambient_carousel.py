"""Mobius v0.8 regression tests: ambient glance timing and carousel behavior."""
import os
from datetime import datetime

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from mobius.ambient import GlanceController, PowerState, clock_label


def test_glance_rotates_and_returns_to_eyes_after_ten_seconds():
    controller = GlanceController(interval_seconds=30, duration_seconds=10, start_now=0)
    choices = [("clock", "10:35", "#FAFAFC"), ("battery", "64% Charging", "#FAFAFC")]
    assert controller.tick(29, choices) == "eyes"
    assert controller.tick(30, choices) == "clock"
    assert controller.message == "10:35"
    assert controller.tick(39.9, choices) == "clock"
    assert controller.tick(40, choices) == "eyes"
    assert controller.message == ""
    assert controller.tick(69, choices) == "eyes"
    assert controller.tick(70, choices) == "battery"
    assert controller.tick(80, choices) == "eyes"


def test_power_event_interrupts_periodic_cycle_and_expires():
    controller = GlanceController(interval_seconds=35, duration_seconds=10, start_now=100)
    controller.show("battery", "Charger unplugged", 108, "#FF6C63")
    assert controller.tick(117, []) == "battery"
    assert controller.accent == "#FF6C63"
    assert controller.tick(118, []) == "eyes"


def test_power_labels_and_clock():
    assert PowerState(42, False).label == "42% Battery"
    assert PowerState(87, True).label == "87% Charging"
    assert PowerState(10, False).accent == "#FF6C63"
    assert PowerState(70, True).accent == "#F7F7F9"
    assert clock_label(datetime(2026, 11, 4, 10, 35)) == "10:35  ·  04 Nov"


def test_six_page_carousel_navigation_and_dark_feature_accents():
    from PySide6.QtWidgets import QApplication, QFrame
    from mobius.carousel import IslandCarousel
    app = QApplication.instance() or QApplication([])
    carousel = IslandCarousel()
    pages = [QFrame() for _ in range(6)]
    names = ["Music", "Lyrics", "Focus Timer", "Water Reminder", "File Studio", "Assistant"]
    colors = ["#C88BFF", "#75C6FF", "#F0B56D", "#4BBEFF", "#E5E7EB", "#A6EE74"]
    for page, name, color in zip(pages, names, colors):
        carousel.add_page(page, name, color)
    assert carousel.current_index == 0
    assert carousel.pages[0].isVisibleTo(carousel.viewport) is False or carousel.pages[0].isHidden() is False
    assert len(carousel.dots) == 6
    carousel.go_to(3, animated=False)
    assert carousel.current_index == 3
    assert carousel.title.text() == "Water Reminder"
    assert carousel.pages[0].isHidden()
    assert not carousel.pages[3].isHidden()
    carousel.step(1)
    assert carousel.current_index == 4
    carousel.go_to(5, animated=False)
    assert carousel.current_index == 5
    carousel.stop()
    carousel.deleteLater()


def test_ui_keeps_studio_and_voice_as_independent_pages():
    from pathlib import Path
    source = (Path(__file__).resolve().parents[1] / "mobius" / "ui.py").read_text(encoding="utf-8")
    assert 'self.carousel.add_page(self.file_page, "File Studio"' in source
    assert 'self.carousel.add_page(self.assistant_page, "Assistant"' in source
    assert "self.radial.show_centered()" in source
    assert "self._glance.tick(now, options)" in source
