"""Full Qt construction regression test for the six-page Mobius island.

Prevents the historical 'window launches then vanishes/crashes' class of errors
caused by mismatched widget attributes or invalid Qt parent/layout moves.
No microphone, WinRT session, shell command or network work is performed.
"""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def test_mobius_window_initializes_all_carousel_pages(monkeypatch):
    from PySide6.QtWidgets import QApplication
    import mobius.ui as ui
    from mobius.media_bridge import MediaBridge

    app = QApplication.instance() or QApplication([])
    monkeypatch.setattr(ui.MobiusWindow, "_setup_tray",
                        lambda self: setattr(self, "tray", None))
    monkeypatch.setattr(ui.RecoveryHotkey, "start", lambda self: None)
    monkeypatch.setattr(ui.RecoveryHotkey, "stop", lambda self: None)
    monkeypatch.setattr(MediaBridge, "refresh", lambda self: None)

    window = ui.MobiusWindow()
    assert len(window.carousel.pages) == 6
    assert window.carousel.labels == [
        "Music", "Lyrics", "Focus Timer", "Water Reminder", "File Studio", "Assistant"
    ]
    assert window.carousel.pages[4] is window.file_page
    assert window.carousel.pages[5] is window.assistant_page

    window.carousel.go_to(4, animated=False)
    assert window.carousel.current_index == 4
    window.set_expanded(True)
    assert window._expanded
    window.carousel.go_to(0, animated=False)
    assert window.carousel.current_index == 0
    window.visibility_timer.stop()
    window.stop_voice()
    window.close()
    window.deleteLater()
