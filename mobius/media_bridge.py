"""Windows system-wide media controls for Mobius.

Uses WinRT GSMTC, not Spotify/Apple/YouTube credentials or private APIs.
Players appear here ONLY if they publish a Windows media session.
All potentially slow WinRT calls execute outside the Qt GUI thread.
"""
from __future__ import annotations

import asyncio
import sys
from concurrent.futures import ThreadPoolExecutor

from PySide6.QtCore import QObject, QTimer, Signal


def _as_seconds(value) -> float:
    try:
        return max(0.0, float(value.total_seconds()))
    except (AttributeError, TypeError, ValueError):
        return 0.0


def _status(value) -> str:
    return str(getattr(value, "name", value)).split(".")[-1].lower()


def _manager_type():
    from winrt.windows.media.control import GlobalSystemMediaTransportControlsSessionManager
    return GlobalSystemMediaTransportControlsSessionManager


async def _session():
    manager = await _manager_type().request_async()
    return manager.get_current_session()


async def _snapshot():
    session = await _session()
    if session is None:
        return {"available": False, "error": "No active Windows media session"}
    props = await session.try_get_media_properties_async()
    playback = session.get_playback_info()
    timeline = session.get_timeline_properties()
    return {
        "available": True,
        "title": str(getattr(props, "title", "") or ""),
        "artist": str(getattr(props, "artist", "") or ""),
        "album": str(getattr(props, "album_title", "") or ""),
        "source": str(session.source_app_user_model_id or ""),
        "status": _status(playback.playback_status),
        "position": _as_seconds(timeline.position),
        "duration": _as_seconds(timeline.end_time),
        "can_seek": bool(getattr(playback.controls, "is_playback_position_enabled", False)),
    }


async def _control(action: str, seconds: float | None = None):
    session = await _session()
    if session is None:
        raise RuntimeError("No supported media player is active")
    if action == "toggle":
        return bool(await session.try_toggle_play_pause_async())
    if action == "play":
        return bool(await session.try_play_async())
    if action == "pause":
        return bool(await session.try_pause_async())
    if action == "next":
        return bool(await session.try_skip_next_async())
    if action == "previous":
        return bool(await session.try_skip_previous_async())
    if action == "seek":
        if seconds is None or seconds < 0:
            return False
        # GSMTC expects position as WinRT 100-nanosecond ticks.
        return bool(await session.try_change_playback_position_async(int(seconds * 10_000_000)))
    raise ValueError("Unsupported media command")


class MediaBridge(QObject):
    snapshot = Signal(object)
    message = Signal(str)
    error = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="MobiusMedia")
        self._busy = False
        self._last = None
        self._timer = QTimer(self)
        self._timer.setInterval(2600)
        self._timer.timeout.connect(self.refresh)
        self._timer.start()
        self.refresh()

    def _submit(self, coro, *, success=None, reading=False):
        if sys.platform != "win32":
            if not reading:
                self.error.emit("Media controls require Windows 10/11")
            return
        if reading and self._busy:
            return
        if reading:
            self._busy = True
        future = self._pool.submit(asyncio.run, coro)

        def finished(f):
            if reading:
                self._busy = False
            try:
                result = f.result()
                if reading:
                    # Qt signal delivery ensures widgets update on the GUI thread.
                    if result != self._last:
                        self._last = result
                        self.snapshot.emit(result)
                elif result:
                    self.message.emit(success or "Media action completed")
                else:
                    self.error.emit("Your player did not accept that command")
            except ModuleNotFoundError:
                self.error.emit("Install optional Windows media support (install-media-windows.bat)")
            except Exception as exc:
                self.error.emit("Media control unavailable: " + str(exc)[:160])

        future.add_done_callback(finished)

    def refresh(self):
        self._submit(_snapshot(), reading=True)

    def control(self, action: str, seconds: float | None = None):
        self._submit(_control(action, seconds), success=f"Media: {action} completed")

    def stop(self):
        self._timer.stop()
        self._pool.shutdown(wait=False, cancel_futures=True)
