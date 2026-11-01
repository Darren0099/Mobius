"""Global Ctrl+Alt+M recovery shortcut for Windows Mobius.

Only emits a Qt signal from a background native message loop.
"""
from __future__ import annotations
import ctypes
import sys
import threading
from ctypes import wintypes
from PySide6.QtCore import QObject, Signal

HOTKEY_ID = 0xB105
WM_HOTKEY = 0x0312
WM_QUIT = 0x0012

class RecoveryHotkey(QObject):
    activated = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._thread = None
        self._thread_id = None
        self._active = threading.Event()

    def start(self):
        if sys.platform != 'win32':
            return
        if self._thread and self._thread.is_alive():
            return
        self._active.set()
        self._thread = threading.Thread(target=self._run, name='Mobius-hotkey',
                                        daemon=True)
        self._thread.start()

    def _run(self):
        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32
        self._thread_id = kernel32.GetCurrentThreadId()
        registered = bool(user32.RegisterHotKey(None, HOTKEY_ID,
                                                 0x0001 | 0x0002 | 0x4000,
                                                 ord('M')))
        if not registered:
            self._thread_id = None
            return  # Shortcut may be in use. System tray still works.
        try:
            msg = wintypes.MSG()
            while self._active.is_set():
                ret = user32.GetMessageW(ctypes.byref(msg), None, 0, 0)
                if ret <= 0:
                    break
                if msg.message == WM_HOTKEY and msg.wParam == HOTKEY_ID:
                    self.activated.emit()
        finally:
            user32.UnregisterHotKey(None, HOTKEY_ID)
            self._thread_id = None

    def stop(self):
        self._active.clear()
        if sys.platform == 'win32' and self._thread_id:
            ctypes.windll.user32.PostThreadMessageW(self._thread_id, WM_QUIT, 0, 0)
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1)
