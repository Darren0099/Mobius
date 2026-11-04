"""Mobius island foreground policy: desktop visible, other apps unobstructed.

All decisions are pure and testable. The Qt window implements the animations;
this policy determines whether it must display fully, as a tiny hint, or hide.
"""
from __future__ import annotations

import ctypes
import sys

DESKTOP_CLASSES = frozenset(("desktop", "progman", "workerw", "shelldll_defview"))


def foreground_class():
    if sys.platform != "win32":
        return "desktop"
    user32 = ctypes.windll.user32
    hwnd = user32.GetForegroundWindow()
    if not hwnd:
        return ""
    buff = ctypes.create_unicode_buffer(256)
    user32.GetClassNameW(hwnd, buff, 256)
    return buff.value


def left_mouse_down():
    return (sys.platform == "win32"
            and bool(ctypes.windll.user32.GetAsyncKeyState(1) & 0x8000))


def visibility_mode(foreground, *, temporary=False, dragging_near_top=False,
                    own_foreground=False, panel_open=False, recovery_available=True,
                    pointer_over_island=False, pinned=False):
    """Return 'expanded', 'compact', 'tip', or 'hidden'.

    Another application's title bar or tabs MUST remain unobstructed by
    default, including if an expanded panel was previously open. Explicit
    hover/hotkey reveal and a cursor currently interacting with Mobius are
    the only reasons a full island may stay up over another application.

    The optional pin setting and missing tray use a minimal 36x6 pixel tip,
    rather than a full-size overlay blocking underlying controls.
    """
    if (foreground or "").casefold() in DESKTOP_CLASSES:
        return "expanded" if panel_open else "compact"

    if own_foreground:
        return "expanded" if panel_open else "compact"

    if temporary or dragging_near_top:
        return "expanded" if panel_open else "compact"

    if pointer_over_island:
        return "expanded" if panel_open else "compact"

    if pinned or not recovery_available:
        return "tip"

    return "hidden"


def should_show(foreground, **kwargs):
    """Compatibility helper for code/tests needing boolean visibility."""
    return visibility_mode(foreground, **kwargs) != "hidden"
