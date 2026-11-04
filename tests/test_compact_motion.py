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
    assert w._animation.endValue().width() == w.TIP_W
    assert w._animation.endValue().height() == w.TIP_H
    w._on_morph_finished()
    assert not w.isVisible()
    w._start_reveal_morph()
    assert w.isVisible()
    assert not w._hide_animating
    assert w._animation.endValue().width() == w.COMPACT_W
    cleanup(w)


def test_tip_is_large_enough_to_accept_file_drop(monkeypatch):
    w = build_window(monkeypatch)
    w.show()
    w._start_tip_morph()
    assert w._tip_mode
    assert w.header.isHidden()  # stripe stays visible while eyes are hidden
    assert w._animation.endValue().width() == w.TIP_W
    assert w._animation.endValue().height() == w.TIP_H
    w._start_reveal_morph()
    assert not w._tip_mode
    assert not w.header.isHidden()
    assert w._animation.endValue().width() == w.COMPACT_W
    cleanup(w)


def test_browser_foreground_collapses_previously_open_panel(monkeypatch):
    from PySide6.QtGui import QCursor
    from PySide6.QtCore import QPoint
    import mobius.ui as ui
    w = build_window(monkeypatch)
    w._recoverable = True
    w._show_over_apps = False
    monkeypatch.setattr(ui, 'foreground_class', lambda: 'Chrome_WidgetWin_1')
    monkeypatch.setattr(ui, 'left_mouse_down', lambda: False)
    monkeypatch.setattr(w, 'isActiveWindow', lambda: False)
    monkeypatch.setattr(w, 'underMouse', lambda: False)
    monkeypatch.setattr(QCursor, 'pos', lambda: QPoint(-1000, -1000))
    w._last_foreground_class = 'WorkerW'
    w.show()
    w.set_expanded(True)
    w._manual_override = True
    w._temporary_until = __import__('time').monotonic() + 300
    w._sync_desktop_visibility()
    assert not w._expanded
    assert not w._manual_override
    assert w._temporary_until == 0
    assert w._hide_animating
    cleanup(w)


def test_hover_reveals_tip_even_when_chrome_is_foreground(monkeypatch):
    import mobius.ui as ui
    from PySide6.QtCore import QPoint
    from PySide6.QtGui import QCursor
    w = build_window(monkeypatch)
    w._recoverable = True
    w._show_over_apps = True
    w.show()
    w._start_tip_morph()
    w._animation.stop()
    assert w._tip_mode
    screen = w._screen()
    top_center = QPoint(screen.x() + screen.width() // 2, screen.y() + 2)
    monkeypatch.setattr(QCursor, "pos", lambda: top_center)
    monkeypatch.setattr(ui, "foreground_class", lambda: "Chrome_WidgetWin_1")
    monkeypatch.setattr(ui, "left_mouse_down", lambda: False)
    monkeypatch.setattr(w, "isActiveWindow", lambda: False)
    monkeypatch.setattr(w, "underMouse", lambda: False)
    w._edge_hover_since = time.monotonic() - 1
    w._sync_desktop_visibility()
    assert not w._tip_mode
    assert w._temporary_until > time.monotonic()
    assert w._animation.endValue().height() == w.COMPACT_H
    cleanup(w)
