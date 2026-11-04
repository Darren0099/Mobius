"""Radial conversion wheel and top-edge file-drop integration tests.

Test without starting any microphone, WinRT player, internet or EXE packaging.
"""
from __future__ import annotations

import math
import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture
def app():
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


def test_wheel_hit_nine_sectors(app):
    from mobius.radial_studio import wheel_hit
    for index in range(9):
        angle = math.radians(-90 + index * 40)
        x = 250 + math.cos(angle) * 140
        y = 256 + math.sin(angle) * 140
        assert wheel_hit(x, y, 500, 500) == index
    assert wheel_hit(250, 256, 500, 500) == -2
    assert wheel_hit(0, 0, 500, 500) == -1


def test_radial_petals_are_closed_valid_shapes(app):
    from PySide6.QtCore import QPointF
    from mobius.radial_studio import RadialStudio
    for i in range(9):
        shape = RadialStudio._petal(i, QPointF(250, 256))
        assert not shape.isEmpty()
        assert shape.elementCount() > 20
        assert shape.boundingRect().width() > 20
        assert shape.boundingRect().height() > 20


def test_only_matching_conversion_options_are_active(tmp_path, app):
    from mobius.radial_studio import eligible_files, eligible_operations
    image = tmp_path / "photo.png"
    pdf1 = tmp_path / "file1.pdf"
    pdf2 = tmp_path / "file2.pdf"
    docx = tmp_path / "report.docx"
    for item in (image, pdf1, pdf2, docx):
        item.write_bytes(b"local test file")
    assert eligible_files([image])
    assert not eligible_files([tmp_path / "missing.jpg"])
    assert not eligible_files([tmp_path / "anything.exe"])
    assert set(eligible_operations([image])) == {"image_pdf", "convert_image"}
    assert "merge_pdf" not in eligible_operations([pdf1])
    assert "merge_pdf" in eligible_operations([pdf1, pdf2])
    assert "word_pdf" in eligible_operations([docx])
    assert "pdf_word" not in eligible_operations([docx])


def test_radial_click_dispatches_selected_operation_only(tmp_path, app):
    from mobius.radial_studio import RadialStudio
    image = tmp_path / "picture.jpg"
    image.write_bytes(b"local")
    menu = RadialStudio()
    menu.set_files([image])
    actions = []
    menu.operation_requested.connect(actions.append)
    assert menu.activate_at(250, 116) == "image_pdf"
    assert actions == ["image_pdf"]
    # The next sector is a PDF-only action, disabled for image input.
    angle = math.radians(-90 + 40)
    assert menu.activate_at(250 + 140 * math.cos(angle),
                            256 + 140 * math.sin(angle)) is None
    assert actions == ["image_pdf"]
    menu.hide()
    menu.deleteLater()


def test_direct_file_drop_on_top_tip_opens_separate_radial(tmp_path, app, monkeypatch):
    from PySide6.QtCore import QPoint, Qt, QMimeData, QUrl
    from PySide6.QtGui import QDragEnterEvent
    from mobius.media_bridge import MediaBridge
    import mobius.ui as ui

    monkeypatch.setattr(ui.MobiusWindow, "_setup_tray",
                        lambda self: setattr(self, "tray", None))
    monkeypatch.setattr(ui.RecoveryHotkey, "start", lambda self: None)
    monkeypatch.setattr(ui.RecoveryHotkey, "stop", lambda self: None)
    monkeypatch.setattr(MediaBridge, "refresh", lambda self: None)
    window = ui.MobiusWindow()
    window.visibility_timer.stop()
    window._island_pulse.stop()
    window.show()
    window._start_tip_morph()
    window._animation.stop()
    assert window._tip_mode
    assert window._show_over_apps  # top-edge line enabled by default
    assert window.isVisible()
    sample = tmp_path / "example.png"
    sample.write_bytes(b"local")
    mime = QMimeData()
    mime.setUrls([QUrl.fromLocalFile(str(sample))])
    drag = QDragEnterEvent(QPoint(25, 5), Qt.DropAction.CopyAction, mime,
                           Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
    window._drag_enter(drag)
    assert drag.isAccepted()
    assert window.pending == [sample]
    assert window.radial.isVisible()
    assert not window._expanded  # the eyes remain independent
    assert window.radial.files == [sample]
    window._animation.stop()
    window.stop_voice()
    window.close()
    window.deleteLater()
