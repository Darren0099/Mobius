"""Mobius v0.8.2: click-away, compact dimensions and window morph regression.

Offscreen unit tests never launch applications or record the microphone.
"""
import os
import time

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def build_window(monkeypatch):
    from PySide6.QtWidgets import QApplication
    from mobius.media_bridge import MediaBridge
    import mobius.ui as ui
    app = QApplication.instance() or QApplication([])
    monkeypatch.setattr(ui.MobiusWindow, "_setup_tray",
                        lambda self: setattr(self, "tray", None))
    monkeypatch.setattr(ui.RecoveryHotkey, "start", lambda self: None)
    monkeypatch.setattr(ui.RecoveryHotkey, "stop", lambda self: None)
    monkeypatch.setattr(MediaBridge, "refresh", lambda self: None)
    window = ui.MobiusWindow()
    window.visibility_timer.stop()
    window._island_pulse.stop()
    return window


def cleanup(window):
    window._animation.stop()
    window.stop_voice()
    window.close()
    window.deleteLater()


def test_click_outside_collapses_panel_without_intercepting_click(monkeypatch):
    from PySide6.QtCore import QPoint
    w = build_window(monkeypatch)
    w.set_expanded(True)
    w._expanded_at = time.monotonic() - 1
    w._manual_override = True
    assert w._dismiss_outside_click(QPoint(-1000, -1000), True, time.monotonic())
    assert not w._expanded
    assert not w._manual_override
    assert w._temporary_until == 0
    cleanup(w)


def test_click_inside_never_closes_expanded_panel(monkeypatch):
    w = build_window(monkeypatch)
    w.set_expanded(True)
    w._expanded_at = time.monotonic() - 1
    center = w.geometry().center()
    assert not w._dismiss_outside_click(center, True, time.monotonic())
    assert w._expanded
    cleanup(w)


def test_global_mouse_hold_not_double_triggered(monkeypatch):
    from PySide6.QtCore import QPoint
    w = build_window(monkeypatch)
    w.set_expanded(True)
    w._expanded_at = time.monotonic() - 1
    w._last_left_down = True
    assert not w._dismiss_outside_click(QPoint(-1000, -1000), True, time.monotonic())
    assert w._expanded
    cleanup(w)


def test_morph_width_and_height_slim_down(monkeypatch):
    w = build_window(monkeypatch)
    assert w.OPEN_W <= 560
    assert w.COMPACT_W <= 165
    assert w._expanded_target_height() <= 240
    w.carousel.go_to(2, animated=False)
    assert w._expanded_target_height() <= 260
    w.carousel.go_to(4, animated=False)
    assert w._expanded_target_height() <= 355
    assert hasattr(w, "tools_scroller")  # all conversion tools remain scrollable
    cleanup(w)


def test_hide_animation_shrinks_instead_of_immediate_hide(monkeypatch):
    w = build_window(monkeypatch)
    w.show()
    w._start_hide_morph()
    assert w._hide_animating
    assert w.isVisible()
    assert w._animation.endValue().width() == 42
    assert w._animation.endValue().height() == 7
    w._on_morph_finished()
    assert not w.isVisible()
    w._start_reveal_morph()
    assert w.isVisible()
    assert not w._hide_animating
    assert w._animation.endValue().width() == w.COMPACT_W
    cleanup(w)
