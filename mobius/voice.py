"""Optional *local* Indonesian speech recognition with faster-whisper.

Two explicit microphone modes: one seven-second utterance, or opt-in
continuous wake-word listening. Audio is never uploaded or stored. Whisper
transcribes locally; only commands starting with 'Mobius' are dispatched.
"""
from __future__ import annotations

import os
import threading
from collections import deque
from pathlib import Path

from PySide6.QtCore import QObject, Signal


def voice_model_dir() -> Path:
    return Path(os.environ.get('MOBIUS_VOICE_MODEL_DIR', str(Path.home() / '.mobius' / 'models')))


class VoiceWorker(QObject):
    success = Signal(str)
    failure = Signal(str)
    finished = Signal()

    def __init__(self, continuous: bool = False):
        super().__init__()
        self.continuous = continuous
        self._stop = threading.Event()

    def stop(self):
        self._stop.set()

    def _transcribe(self, model, audio, np):
        if np.sqrt(float(np.mean(audio ** 2))) < 0.002:
            if not self.continuous:
                self.failure.emit('Tidak terdengar suara. Periksa mikrofon lalu coba lagi.')
            return
        segments, _ = model.transcribe(audio, language='id', beam_size=3,
                                       vad_filter=True, condition_on_previous_text=False)
        command = ' '.join(segment.text for segment in segments).strip()
        if command:
            self.success.emit(command)
        elif not self.continuous:
            self.failure.emit('Suara tidak dikenali. Coba ulangi perintah dengan jelas.')

    def run(self):
        try:
            import numpy as np
            import sounddevice as sd
            from faster_whisper import WhisperModel
            cache = voice_model_dir()
            model = WhisperModel('base', device='cpu', compute_type='int8',
                                 download_root=str(cache), local_files_only=True)
            sr = 16000
            if not self.continuous:
                audio = sd.rec(sr * 7, samplerate=sr, channels=1, dtype='float32')
                sd.wait()
                if not self._stop.is_set():
                    self._transcribe(model, audio.ravel().astype(np.float32), np)
            else:
                # Simple energy-gated local voice activity detector. Idle mic
                # listens only while the user explicitly enables hands-free.
                preroll = deque(maxlen=8)
                frames = []
                silent = 0
                with sd.InputStream(samplerate=sr, channels=1, dtype='float32', blocksize=1600) as stream:
                    while not self._stop.is_set():
                        block, _ = stream.read(1600)
                        samples = block.reshape(-1).copy()
                        is_talking = float(np.sqrt(np.mean(samples ** 2))) > .016
                        if not frames:
                            preroll.append(samples)
                            if is_talking:
                                frames = list(preroll)
                                silent = 0
                            continue
                        frames.append(samples)
                        silent = 0 if is_talking else silent + 1
                        # 1.2s silence ends phrase; 10s max to avoid long clips.
                        if silent >= 12 or len(frames) >= 100:
                            if len(frames) >= 5:
                                self._transcribe(model, np.concatenate(frames).astype(np.float32), np)
                            frames = []
                            preroll.clear()
                            silent = 0
        except ImportError:
            self.failure.emit('Fitur suara belum siap. Jalankan install-voice-windows.bat terlebih dahulu.')
        except Exception as exc:
            self.failure.emit(f'Mikrofon/model suara tidak siap: {exc}')
        finally:
            self.finished.emit()
