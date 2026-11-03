"""Prevent startup regressions from incompatible RecoveryHotkey/UI signals.

Pure syntax inspection keeps this check runnable without a Windows desktop.
"""
import ast
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]


def test_hotkey_declares_every_signal_connected_by_ui():
    hotkey = ast.parse((ROOT / "mobius" / "hotkey.py").read_text(encoding="utf-8"))
    klass = next(node for node in hotkey.body
                 if isinstance(node, ast.ClassDef) and node.name == "RecoveryHotkey")
    signals = {
        target.id
        for node in klass.body if isinstance(node, ast.Assign)
        for target in node.targets if isinstance(target, ast.Name)
        if isinstance(node.value, ast.Call)
        and isinstance(node.value.func, ast.Name)
        and node.value.func.id == "Signal"
    }
    ui_source = (ROOT / "mobius" / "ui.py").read_text(encoding="utf-8")
    connected = set(re.findall(r"self\\._recovery_hotkey\\.(\\w+)\\.connect\\(", ui_source))
    assert connected, "No RecoveryHotkey Qt signal connections found in UI"
    assert connected <= signals, f"Undeclared RecoveryHotkey signals: {connected - signals}"


def test_hotkey_unavailable_is_safe_fallback():
    source = (ROOT / "mobius" / "hotkey.py").read_text(encoding="utf-8")
    assert "unavailable = Signal(str)" in source
    assert "self.unavailable.emit(" in source
    assert "return  # Non-fatal:" in source
