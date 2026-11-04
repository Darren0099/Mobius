"""Verify robust debug launch wiring without a physical Windows desktop."""
from pathlib import Path

from mobius.startup_trace import trace_startup


def test_debug_trace_writes_stage_to_file(tmp_path, monkeypatch):
    import mobius.startup_trace as module
    monkeypatch.setenv("MOBIUS_DEBUG_STARTUP", "1")
    monkeypatch.setattr(module, "LOG_DIR", tmp_path)
    trace_startup("Before QApplication constructor")
    assert "Before QApplication constructor" in (tmp_path / "mobius-startup.log").read_text(encoding="utf-8")


def test_unset_debug_trace_does_not_create_file(tmp_path, monkeypatch):
    import mobius.startup_trace as module
    monkeypatch.delenv("MOBIUS_DEBUG_STARTUP", raising=False)
    monkeypatch.setattr(module, "LOG_DIR", tmp_path)
    trace_startup("Silent")
    assert not (tmp_path / "mobius-startup.log").exists()


def test_debug_mode_forces_visual_overlay():
    root = Path(__file__).resolve().parents[1]
    ui = (root / "mobius" / "ui.py").read_text(encoding="utf-8")
    assert "MOBIUS_DEBUG_VISIBLE" in ui
    assert "QTimer.singleShot(350, window.force_expand)" in ui
    debug = (root / "run-debug-windows.bat").read_text(encoding="utf-8")
    assert "set \"MOBIUS_DEBUG_VISIBLE=1\"" in debug
    assert "set \"MOBIUS_DEBUG_STARTUP=1\"" in debug


def test_qt_doctor_does_not_load_whisper_or_media():
    root = Path(__file__).resolve().parents[1]
    script = (root / "scripts" / "qt_doctor.py").read_text(encoding="utf-8")
    assert "QApplication([" in script
    assert "from mobius.ui" not in script
    assert "faster_whisper" not in script
