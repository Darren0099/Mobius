"""Minimal startup-stage logging shared by the EXE and source launchers."""
import os
from datetime import datetime
from pathlib import Path


LOG_DIR = Path.home() / "Documents" / "Mobius"


def trace_startup(stage: str) -> None:
    if os.environ.get("MOBIUS_DEBUG_STARTUP") != "1":
        return
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    message = f"[{datetime.now().isoformat(timespec='seconds')}] {stage}"
    print(message, flush=True)
    with (LOG_DIR / "mobius-startup.log").open("a", encoding="utf-8") as log:
        log.write(message + "\n"
        )
