"""Regression tests for Explorer auto-reveal and staged radial fan animation."""
from __future__ import annotations

from pathlib import Path

import pytest


def test_explorer_selects_single_generated_file(tmp_path):
    from mobius.result_reveal import explorer_arguments, reveal_target
    pdf = tmp_path / "finished.pdf"
    pdf.write_bytes(b"pdf")
    assert reveal_target([pdf], tmp_path) == (pdf.resolve(), True)
    assert explorer_arguments([pdf], tmp_path) == [
        "explorer.exe", "/select,", str(pdf.resolve())
    ]


def test_explorer_opens_output_folder_for_multiple_results(tmp_path):
    from mobius.result_reveal import explorer_arguments, reveal_target
    files = [tmp_path / "page-1.png", tmp_path / "page-2.png"]
    for file in files:
        file.write_bytes(b"png")
    assert reveal_target(files, tmp_path) == (tmp_path.resolve(), False)
    assert explorer_arguments(files, tmp_path) == ["explorer.exe", str(tmp_path.resolve())]


def test_missing_or_failed_outputs_do_not_open_explorer(tmp_path):
    from mobius.result_reveal import explorer_arguments, reveal_target
    assert reveal_target([], tmp_path) is None
    assert explorer_arguments([tmp_path / "missing.pdf"], tmp_path) is None


def test_auto_reveal_calls_safe_explorer_argv_on_windows(tmp_path, monkeypatch):
    import mobius.result_reveal as reveal
    file = tmp_path / "done.pdf"
    file.write_bytes(b"done")
    seen = []
    monkeypatch.setattr(reveal.sys, "platform", "win32")
    assert reveal.reveal_results([file], tmp_path, launch=lambda argv: seen.append(argv))
    assert seen == [["explorer.exe", "/select,", str(file.resolve())]]


def test_fan_unfolds_pieces_in_order():
    from mobius.radial_studio import fan_piece_progress
    assert fan_piece_progress(0, 0, 9) == 0
    assert fan_piece_progress(.28, 0, 9) > 0.5
    assert fan_piece_progress(.28, 8, 9) == 0
    assert fan_piece_progress(.65, 1, 9) == 1
    assert 0 < fan_piece_progress(.65, 8, 9) < 1
    assert fan_piece_progress(1, 8, 9) == 1
    assert fan_piece_progress(.5, 9, 9) == 0


def test_radial_opens_from_single_leaf_and_ends_full_circle(qtbot_placeholder=None):
    # Pure geometry test: constructing the polygon does not require a Qt window.
    from PySide6.QtCore import QPointF
    from mobius.radial_studio import RadialStudio
    center = QPointF(225, 231)
    small = RadialStudio._petal(5, center, opening=.02)
    unfolded = RadialStudio._petal(5, center, opening=1)
    assert unfolded.boundingRect().width() > small.boundingRect().width()
    assert unfolded.elementCount() >= 40


def test_ui_success_triggers_delayed_reveal(monkeypatch, tmp_path):
    import os
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication
    from mobius.engine import Result
    from mobius.media_bridge import MediaBridge
    import mobius.ui as ui

    app = QApplication.instance() or QApplication([])
    monkeypatch.setattr(ui.MobiusWindow, "_setup_tray", lambda self: setattr(self, "tray", None))
    monkeypatch.setattr(ui.RecoveryHotkey, "start", lambda self: None)
    monkeypatch.setattr(ui.RecoveryHotkey, "stop", lambda self: None)
    monkeypatch.setattr(MediaBridge, "refresh", lambda self: None)
    window = ui.MobiusWindow()
    window.visibility_timer.stop()
    window._island_pulse.stop()
    output = tmp_path / "converted.pdf"
    output.write_bytes(b"ok")
    called = []
    monkeypatch.setattr(window.feedback, "speak", lambda _: None)
    monkeypatch.setattr(ui, "reveal_results", lambda paths, dest: called.append((paths, dest)) or True)
    monkeypatch.setattr(ui.QTimer, "singleShot", lambda delay, callback: callback())
    window._success(Result(files=[output]))
    assert called == [((output,), window.destination)]
    window._animation.stop()
    window.stop_voice()
    window.close()
    window.deleteLater()


def test_gradient_island_and_fan_paint_offscreen_without_qt_errors(monkeypatch):
    import os
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QPixmap
    from PySide6.QtWidgets import QApplication
    from mobius.media_bridge import MediaBridge
    import mobius.ui as ui

    app = QApplication.instance() or QApplication([])
    monkeypatch.setattr(ui.MobiusWindow, "_setup_tray", lambda self: setattr(self, "tray", None))
    monkeypatch.setattr(ui.RecoveryHotkey, "start", lambda self: None)
    monkeypatch.setattr(ui.RecoveryHotkey, "stop", lambda self: None)
    monkeypatch.setattr(MediaBridge, "refresh", lambda self: None)
    window = ui.MobiusWindow()
    window.visibility_timer.stop()
    window._island_pulse.stop()
    window.show()
    window._animation.stop()
    window.resize(window.COMPACT_W, window.COMPACT_H)
    compact = QPixmap(window.size())
    compact.fill(Qt.GlobalColor.transparent)
    window.render(compact)
    assert not compact.isNull()
    top = compact.toImage().pixelColor(window.width() // 2, 2)
    bottom = compact.toImage().pixelColor(window.width() // 2 + 18, window.height() - 2)
    assert top.alpha() > 0
    assert bottom.alpha() > 0
    assert (top.red(), top.green(), top.blue()) != (bottom.red(), bottom.green(), bottom.blue())

    wheel = window.radial
    wheel._fan_progress = .5
    halfway = QPixmap(wheel.size())
    halfway.fill(Qt.GlobalColor.transparent)
    wheel.render(halfway)
    wheel._fan_progress = 1.0
    expanded = QPixmap(wheel.size())
    expanded.fill(Qt.GlobalColor.transparent)
    wheel.render(expanded)
    assert not halfway.isNull() and not expanded.isNull()

    window._animation.stop()
    window.stop_voice()
    window.close()
    window.deleteLater()
