"""Windows entrypoint with optional startup tracing for hidden/hung Qt windows."""
from __future__ import annotations

import os
import sys
import traceback
from datetime import datetime
from pathlib import Path
from mobius.startup_trace import trace_startup

LOG_DIR = Path.home() / "Documents" / "Mobius"


def crash_logger(error_type, error, tb):
    if issubclass(error_type, KeyboardInterrupt):
        trace_startup("Interrupted by Ctrl+C (not evidence of an application crash)")
        return sys.__excepthook__(error_type, error, tb)
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    message = "".join(traceback.format_exception(error_type, error, tb))
    with (LOG_DIR / "mobius-error.log").open("a", encoding="utf-8") as log:
        log.write(message + "\n")
    trace_startup(f"Uncaught {error_type.__name__}: {error}")
    if sys.platform == "win32":
        import ctypes
        ctypes.windll.user32.MessageBoxW(
            0,
            f"Gagal menjalankan Mobius. Detail: {LOG_DIR / 'mobius-error.log'}\n\n{str(error)[:300]}",
            "Mobius Error",
            0x10,
        )
    else:
        print(message, file=sys.stderr)


sys.excepthook = crash_logger

if __name__ == "__main__":
    trace_startup("Python entrypoint started")
    from mobius.ui import start
    trace_startup("Imported Mobius UI and dependencies")
    start()
