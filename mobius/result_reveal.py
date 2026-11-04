"""Reveal successful offline conversions in the system file manager.

No upload and no shell execution: explorer.exe receives explicit arguments.
Call only after a successful conversion that produced existing files.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def reveal_target(files, destination: Path) -> tuple[Path, bool] | None:
    """Return (existing target, select_file) or None for an empty result."""
    existing = [Path(item).resolve() for item in files if Path(item).is_file()]
    if not existing:
        return None
    if len(existing) == 1:
        return existing[0], True
    folders = {item.parent for item in existing}
    if len(folders) == 1:
        return next(iter(folders)), False
    destination = Path(destination).resolve()
    if destination.is_dir():
        return destination, False
    return existing[0].parent, False


def explorer_arguments(files, destination: Path) -> list[str] | None:
    """Create a safe Explorer argument vector for easy testing."""
    result = reveal_target(files, destination)
    if result is None:
        return None
    target, select_file = result
    if select_file:
        return ["explorer.exe", "/select,", str(target)]
    return ["explorer.exe", str(target)]


def reveal_results(files, destination: Path, *, launch=None) -> bool:
    """Open Explorer (Windows) or the desktop file manager (other OS).

    Returns False if the files are missing or if the OS cannot open them.
    The optional launcher permits tests without actually opening windows.
    """
    target = reveal_target(files, destination)
    if target is None:
        return False
    path, select_file = target
    if sys.platform == "win32":
        args = explorer_arguments(files, destination)
        try:
            (launch or subprocess.Popen)(args)
            return True
        except (OSError, ValueError):
            return False
    from PySide6.QtCore import QUrl
    from PySide6.QtGui import QDesktopServices

    location = path.parent if select_file else path
    return bool(QDesktopServices.openUrl(QUrl.fromLocalFile(str(location))))
