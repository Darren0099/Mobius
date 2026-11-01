"""Keep the small island off other apps, while allowing brief drag reveal."""
import ctypes
import sys

def foreground_class():
    if sys.platform != 'win32': return 'desktop'
    user32 = ctypes.windll.user32
    hwnd = user32.GetForegroundWindow()
    buff = ctypes.create_unicode_buffer(256)
    user32.GetClassNameW(hwnd, buff, 256)
    return buff.value

def left_mouse_down():
    return sys.platform == 'win32' and bool(ctypes.windll.user32.GetAsyncKeyState(1) & 0x8000)

def should_show(foreground, *, temporary=False, dragging_near_top=False, own_foreground=False):
    return bool(temporary or dragging_near_top or own_foreground or foreground.lower() in ('desktop','progman','workerw'))
