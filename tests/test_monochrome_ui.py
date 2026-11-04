"""Monochrome Mobius design: small status pills and genuine local vector icons."""
import os
import time

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def test_all_vector_icons_render_without_font_or_network():
    from PySide6.QtWidgets import QApplication
    from mobius.vector_icons import icon
    app = QApplication.instance() or QApplication([])
    for name in (
        "battery", "charging", "clock", "music", "timer", "water",
        "lyrics", "file", "pdf", "word", "image", "folder", "mic",
        "external", "left", "right", "play", "pause", "next", "previous",
        "reset", "search", "assistant", "indicator"
    ):
        result = icon(name, 18)
        assert not result.isNull(), name
        assert not result.pixmap(18, 18).isNull(), name


def test_small_monochrome_glance_sizing(monkeypatch):
    from PySide6.QtWidgets import QApplication
    from mobius.media_bridge import MediaBridge
    from mobius.ambient import PowerState
    import mobius.ui as ui
    app = QApplication.instance() or QApplication([])
    monkeypatch.setattr(ui.MobiusWindow, "_setup_tray",
                        lambda self: setattr(self, "tray", None))
    monkeypatch.setattr(ui.RecoveryHotkey, "start", lambda self: None)
    monkeypatch.setattr(ui.RecoveryHotkey, "stop", lambda self: None)
    monkeypatch.setattr(MediaBridge, "refresh", lambda self: None)
    monkeypatch.setattr(ui, "read_windows_power", lambda: PowerState(29, True))
    w = ui.MobiusWindow()
    w.visibility_timer.stop()
    w._island_pulse.stop()

    assert w.COMPACT_W <= 130
    assert w.OPEN_W <= 420
    assert w.eyes.width() <= 100
    w._glance.show("battery", "29% Charging  12:56", time.monotonic())
    w._refresh_island_status()
    assert 150 <= w._compact_width <= 240
    assert "29%" in w.island_status.text()
    assert not w.island_glance_icon.pixmap().isNull()
    assert w.island_status.styleSheet().find("#FAFAFC") >= 0
    w._animation.stop()
    w.stop_voice()
    w.close()
    w.deleteLater()


def test_visible_ui_strings_have_no_emoji_icons():
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    sources = "\n".join(
        (root / file).read_text(encoding="utf-8")
        for file in ("mobius/ui.py", "mobius/ambient.py",
                     "mobius/quick_deck.py", "mobius/carousel.py")
    )
    # No emoji or formerly substituted symbolic Unicode button glyphs.
    banned = (
        "\U0001f50b", "\u266b", "\u266a", "\u25b0",
        "\u25c9", "\u25cf", "\u25ce", "\u23ee",
        "\u23ed", "\u23ef", "\u25a4", "\u2197",
    )
    assert all(char not in sources for char in banned)
