"""Offline English spoken feedback for completed Windows actions.

SAPI 5 ships with Windows. Speaking is asynchronous and NEVER executes
dictated text as a shell command or sends text to any web service.
"""
from __future__ import annotations

import queue
import re
import sys
import threading
import time


def english_confirmation(intent, result: str) -> str | None:
    """Only narrate success actually reported by the action runner."""
    if not isinstance(result, str):
        return None
    kind = getattr(intent, 'kind', '')
    if kind == 'apps' and result.startswith('Aplikasi dibuka:'):
        names = list(getattr(intent, 'args', {}).get('apps', []))
        if len(names) == 1:
            title = 'calculator' if names[0] == 'kalkulator' else names[0]
            return f"Okay, {title} is now open."
        return "Okay, I have opened the requested applications."
    if kind == 'search' and result.startswith('Pencarian dibuka'):
        query = str(getattr(intent, 'args', {}).get('query', '')).strip()
        # Indonesian search terms remain in the browser; only voice feedback is English.
        if query.lower().startswith('resep '):
            query = 'recipes for ' + query[6:]
        query = re.sub(r'[^a-zA-Z0-9\s,.!?-]', ' ', query)
        query = re.sub(r'\s+', ' ', query).strip()[:95]
        return f"Okay, I opened the browser search for {query}." if query else "Okay, I opened the search results in your browser."
    if kind == 'browser' and result == 'Browser dibuka.':
        return "Okay, your browser is open."
    if kind == 'music' and result.startswith('Memutar musik acak:'):
        return "Okay, your music is playing."
    if kind == 'shutdown' and result.startswith('Shutdown terjadwal'):
        return "Okay, the computer shutdown has been scheduled."
    if kind == 'cancel_shutdown' and result.startswith('Shutdown berhasil dibatalkan'):
        return "Okay, the scheduled shutdown has been cancelled."
    if kind == 'convert' and result.startswith('Selesai:'):
        return "Okay, your file conversion is complete."
    return None


class SpeechFeedback:
    """Background, queue-based Windows TTS; active event suppresses microphone echo."""

    def __init__(self):
        self.playing = threading.Event()
        self._stop = threading.Event()
        self._items = queue.Queue(maxsize=8)
        self._thread = None
        self._lock = threading.Lock()

    def speak(self, message: str):
        if sys.platform != 'win32' or not message or self._stop.is_set():
            return
        with self._lock:
            if self._thread is None:
                self._thread = threading.Thread(target=self._run, name='Mobius-English-TTS', daemon=True)
                self._thread.start()
            try:
                self.playing.set()
                self._items.put_nowait(message.replace('\n', ' ').strip()[:220])
            except queue.Full:
                pass

    def _run(self):
        import pythoncom
        voice = None
        initialized = False
        try:
            pythoncom.CoInitialize()
            initialized = True
            import win32com.client
            voice = win32com.client.Dispatch('SAPI.SpVoice')
            voice.Rate = 0
            voice.Volume = 92
            try:
                english = voice.GetVoices('Language=409')
                if english.Count:
                    voice.Voice = english.Item(0)
            except Exception:
                pass  # Fallback to user-selected Windows voice.
        except Exception:
            voice = None  # Missing TTS should never take down the assistant.
        try:
            while not self._stop.is_set():
                try:
                    phrase = self._items.get(timeout=0.2)
                except queue.Empty:
                    continue
                if phrase is None:
                    break
                try:
                    if voice is not None:
                        voice.Speak(phrase)
                except Exception:
                    pass
                finally:
                    self._items.task_done()
                    # Delay mic reopening to avoid the tail of loudspeaker audio.
                    time.sleep(0.4)
                    if self._items.empty():
                        self.playing.clear()
        finally:
            self.playing.clear()
            if initialized:
                try:
                    pythoncom.CoUninitialize()
                except Exception:
                    pass

    def stop(self):
        self._stop.set()
        try:
            self._items.put_nowait(None)
        except queue.Full:
            pass
        if self._thread is not None:
            self._thread.join(timeout=2.0)
        self.playing.clear()
