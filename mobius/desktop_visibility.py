"""When to display the compact island without interrupting other applications.

Expanded panels must not vanish while the user is working with controls.
"""
import ctypes
import sys

DESKTOP_CLASSES = frozenset(('desktop', 'progman', 'workerw', 'shelldll_defview'))

def foreground_class():
    if sys.platform != 'win32': return 'desktop'
    user32 = ctypes.windll.user32
    hwnd = user32.GetForegroundWindow()
    if not hwnd: return ''
    buff = ctypes.create_unicode_buffer(256)
    user32.GetClassNameW(hwnd, buff, 256)
    return buff.value

def left_mouse_down():
    return sys.platform == 'win32' and bool(ctypes.windll.user32.GetAsyncKeyState(1) & 0x8000)

def should_show(foreground, *, temporary=False, dragging_near_top=False,
                own_foreground=False, panel_open=False, recovery_available=True,
                pointer_over_island=False, pinned=False):
    """Return visible if user intentionally interacts, otherwise desktop-only.

    Never hide the only available control when there is no system tray.
    """
    if (not recovery_available or pinned or panel_open or temporary
            or dragging_near_top or own_foreground or pointer_over_island):
        return True
    return (foreground or '').casefold() in DESKTOP_CLASSES
