"""Source-only tests for Mobius sunset theme, animated robot and radial menus."""
import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture
def qapp():
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


def test_theme_gradient_really_transitions_orange_to_red(qapp):
    from mobius.theme import ORANGE, CORAL, RED, gradient
    g = gradient(0, 0, 250, 0)
    stops = g.stops()
    assert len(stops) == 3
    assert [str(c.name()).lower() for _, c in stops] == [
        ORANGE.lower(), CORAL.lower(), RED.lower()
    ]


def test_robot_has_distinct_expressions_and_mouths(qapp):
    from PySide6.QtGui import QPainter, QPixmap
    from PySide6.QtCore import Qt
    from mobius.robot_eyes import Eyes, EXPRESSIONS
    face = Eyes()
    assert face.width() <= 100 and face.height() <= 32
    assert {"happy", "thinking", "warning", "surprised", "angry"}.issubset(EXPRESSIONS)
    for expression in ("neutral", "happy", "smile", "kiss", "sad", "surprised",
                       "focus", "angry", "sleepy", "sleep", "wink"):
        image = QPixmap(94, 29)
        image.fill(Qt.GlobalColor.transparent)
        painter = QPainter(image)
        face._draw(painter, expression)
        painter.end()
        assert not image.isNull()
    face._timer.stop()
    face.deleteLater()


def test_radial_enabled_slices_ease_out_only_when_valid(tmp_path, qapp):
    from mobius.radial_studio import RadialStudio, wheel_hit
    picture = tmp_path / "portrait.png"
    picture.write_bytes(b"local")
    wheel = RadialStudio()
    wheel.set_files([picture])
    assert wheel.width() <= 460 and wheel.height() <= 460
    wheel.highlight = 0  # Image -> PDF is eligible.
    for _ in range(20):
        wheel._animate()
    assert wheel.pop_distance(0) >= 14
    assert wheel.pop_distance(1) == 0  # PDF -> Image disabled for a PNG.
    # Active slice stays clickable even when its offset extends the radius.
    assert wheel_hit(wheel.width()/2, wheel.height()/2 + 6 - 213,
                     wheel.width(), wheel.height()) == 0
    wheel.highlight = -1
    for _ in range(20):
        wheel._animate()
    assert wheel.pop_distance(0) < 5
    wheel.hide()
    wheel.deleteLater()


def test_animated_progress_arcs_clamp_and_settle(qapp):
    from PySide6.QtGui import QPixmap
    from mobius.arc_meter import ArcMeter
    arc = ArcMeter("timer", 76)
    arc.set_fraction(-2)
    for _ in range(30):
        arc._animate()
    assert 0 <= arc._value <= .01
    arc.set_fraction(2)
    for _ in range(30):
        arc._animate()
    assert .98 <= arc._value <= 1
    canvas = QPixmap(76, 76)
    canvas.fill()
    arc.render(canvas)
    assert not canvas.isNull()
    arc._timer.stop()
    arc.deleteLater()


def test_compact_focus_water_and_music_controls(qapp, monkeypatch):
    from mobius.media_bridge import MediaBridge
    monkeypatch.setattr(MediaBridge, "refresh", lambda self: None)
    from mobius.quick_deck import QuickDeck
    deck = QuickDeck()
    assert deck.focus_ring.width() <= 80
    assert deck.water_ring.width() <= 70
    assert deck.water_stack.count() == 2
    assert deck.water_stack.currentIndex() == 0
    deck.water_stack.setCurrentIndex(1)
    assert deck.water_stack.currentIndex() == 1
    deck.water_stack.setCurrentIndex(0)
    deck._render_focus()
    deck._render_water()
    assert deck.water_total.text().endswith("ml")
    assert deck.track is not None
    deck.stop()
    deck.deleteLater()


def test_foreground_tip_is_black_small_and_desk_uses_eyes(qapp, monkeypatch):
    import mobius.ui as ui
    from mobius.media_bridge import MediaBridge
    from PySide6.QtGui import QCursor
    from PySide6.QtCore import QPoint
    monkeypatch.setattr(ui.MobiusWindow, "_setup_tray",
                        lambda self: setattr(self, "tray", None))
    monkeypatch.setattr(ui.RecoveryHotkey, "start", lambda self: None)
    monkeypatch.setattr(ui.RecoveryHotkey, "stop", lambda self: None)
    monkeypatch.setattr(MediaBridge, "refresh", lambda self: None)
    window = ui.MobiusWindow()
    window.visibility_timer.stop()
    window._island_pulse.stop()
    assert window.TIP_W <= 100
    assert window.TIP_H <= 14
    monkeypatch.setattr(ui, "foreground_class", lambda: "Chrome_WidgetWin_1")
    monkeypatch.setattr(ui, "left_mouse_down", lambda: False)
    monkeypatch.setattr(QCursor, "pos", lambda: QPoint(-1000, -1000))
    monkeypatch.setattr(window, "isActiveWindow", lambda: False)
    monkeypatch.setattr(window, "underMouse", lambda: False)
    window._sync_desktop_visibility()
    assert window._tip_mode
    monkeypatch.setattr(ui, "foreground_class", lambda: "WorkerW")
    window._sync_desktop_visibility()
    assert not window._tip_mode
    assert window._animation.endValue().height() == window.COMPACT_H
    window._animation.stop()
    window.stop_voice()
    window.close()
    window.deleteLater()
