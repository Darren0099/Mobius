"""Minimal Qt startup diagnostic for Windows.

Does not import Mobius, Whisper, PDF engines or WinRT.
If this hangs, debug the Qt installation/display rather than voice commands.
"""
from __future__ import annotations
import os
import sys
import time
import traceback


def report(msg):
    print(f"[Qt Doctor {time.strftime('%H:%M:%S')}] {msg}", flush=True)


def main():
    report(f"Python executable: {sys.executable}")
    report(f"Python version: {sys.version.split()[0]}")
    report(f"Windows desktop session: {os.environ.get('SESSIONNAME', '<unspecified>')}")
    for var in ('QT_QPA_PLATFORM', 'QT_QPA_PLATFORM_PLUGIN_PATH', 'QT_PLUGIN_PATH'):
        if os.environ.get(var):
            report(f"Qt variable {var} is externally set: {os.environ[var]}")
    report("Importing PySide6 QtCore / QtWidgets")
    from PySide6.QtCore import QLibraryInfo, QTimer, qVersion
    from PySide6.QtWidgets import QApplication, QLabel, QWidget, QVBoxLayout
    report(f"Qt version: {qVersion()}")
    report("Creating bare QApplication (NO Mobius modules)")
    app = QApplication(["mobius-qt-doctor"])
    report(f"QApplication ready; platform={app.platformName()}")
    w = QWidget()
    w.setWindowTitle("Mobius Qt Doctor — minimal display")
    layout = QVBoxLayout(w)
    layout.addWidget(QLabel("Qt is working. This test window closes automatically."))
    w.resize(400, 105)
    w.show()
    report("Test window shown. Qt event loop running.")
    QTimer.singleShot(2200, app.quit)
    result = app.exec()
    report(f"Qt event loop finished normally: {result}")
    return result


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception:
        traceback.print_exc()
        raise SystemExit(1)
