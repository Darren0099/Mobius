"""Local hands-free speech recognition for Indonesian, with no wake-word requirement.

Microphone input and transcripts stay on this computer. No cloud STT.
The user can disable listening in the Mobius tray or panel.
"""
from __future__ import annotations

import os
import queue
import threading
from collections import deque
from pathlib import Path

from PySide6.QtCore import QObject, Signal

from .voice_gate import AdaptiveSpeechGate


def voice_model_dir() -> Path:
    return Path(os.environ.get("MOBIUS_VOICE_MODEL_DIR",
                               str(Path.home() / ".mobius" / "models")))


class VoiceWorker(QObject):
    success = Signal(str)
    failure = Signal(str)
    status = Signal(str)
    finished = Signal()

    SAMPLE_RATE = 16000
    BLOCK_SAMPLES = 1600  # 100 ms
    PRE_ROLL_BLOCKS = 6   # never lose the first syllable
    SILENCE_BLOCKS = 8    # finish after 0.8 seconds of relative silence
    MAX_BLOCKS = 120     # cap a single utterance at 12 seconds

    def __init__(self, continuous: bool = True):
        super().__init__()
        self.continuous = continuous
        self._stop = threading.Event()

    def stop(self):
        self._stop.set()

    def _transcribe(self, model, samples, np):
        if self._stop.is_set() or not len(samples):
            return
        rms = float(np.sqrt(np.mean(samples * samples)))
        if rms < 0.0012:
            return
        self.status.emit("Memahami ucapan secara offline...")
        try:
            # Our adaptive gate has already segmented audio. Whisper's default
            # VAD can strip short commands such as 'buka kalkulator'.
            segments, info = model.transcribe(
                samples, language="id", beam_size=3, vad_filter=False,
                condition_on_previous_text=False, no_speech_threshold=0.65,
                initial_prompt="Perintah komputer Bahasa Indonesia: buka kalkulator, "
                               "buka notepad, cari resep di browser, buka Chrome, "
                               "putar musik, ubah PDF menjadi gambar.")
            phrase = " ".join(seg.text for seg in segments).strip()
            if phrase:
                self.success.emit(phrase)
        finally:
            self.status.emit("Mendengarkan perintah...")

    def run(self):
        try:
            import numpy as np
            import sounddevice as sd
            from faster_whisper import WhisperModel

            model_name = os.environ.get("MOBIUS_VOICE_MODEL", "base")
            self.status.emit("Memuat model suara lokal...")
            model = WhisperModel(model_name, device="cpu", compute_type="int8",
                                 download_root=str(voice_model_dir()),
                                 local_files_only=True)
            self.status.emit("Mendengarkan perintah...")

            if not self.continuous:
                audio = sd.rec(7 * self.SAMPLE_RATE, samplerate=self.SAMPLE_RATE,
                               channels=1, dtype="float32")
                sd.wait()
                if not self._stop.is_set():
                    self._transcribe(model, audio.ravel().astype(np.float32), np)
                return

            gate = AdaptiveSpeechGate()
            chunks: queue.Queue = queue.Queue(maxsize=220)

            def on_audio(indata, frames, time_info, status):
                if self._stop.is_set():
                    return
                block = indata[:, 0].copy()
                try:
                    chunks.put_nowait(block)
                except queue.Full:
                    # Never block the real-time PortAudio callback.
                    try:
                        chunks.get_nowait()
                    except queue.Empty:
                        pass
                    try:
                        chunks.put_nowait(block)
                    except queue.Full:
                        pass

            preroll = deque(maxlen=self.PRE_ROLL_BLOCKS)
            phrase_blocks = []
            speech_blocks = 0
            quiet_blocks = 0

            with sd.InputStream(samplerate=self.SAMPLE_RATE, channels=1,
                                dtype="float32", blocksize=self.BLOCK_SAMPLES,
                                callback=on_audio):
                while not self._stop.is_set():
                    try:
                        block = chunks.get(timeout=0.2)
                    except queue.Empty:
                        continue
                    rms = float(np.sqrt(np.mean(block * block)))
                    speaking = gate.is_speech(rms, continuing=bool(phrase_blocks))
                    if not phrase_blocks:
                        preroll.append(block)
                        if speaking:
                            phrase_blocks = list(preroll)
                            speech_blocks = 1
                            quiet_blocks = 0
                        continue

                    phrase_blocks.append(block)
                    if speaking:
                        speech_blocks += 1
                        quiet_blocks = 0
                    else:
                        quiet_blocks += 1

                    if (quiet_blocks >= self.SILENCE_BLOCKS
                            or len(phrase_blocks) >= self.MAX_BLOCKS):
                        if speech_blocks >= 3:
                            audio = np.concatenate(phrase_blocks).astype(np.float32)
                            self._transcribe(model, audio, np)
                        phrase_blocks = []
                        preroll.clear()
                        speech_blocks = 0
                        quiet_blocks = 0

        except ImportError as exc:
            self.failure.emit("Modul suara belum tersedia: " + str(exc)
                              + ". Jalankan install-voice-windows.bat.")
        except Exception as exc:
            self.failure.emit("Mikrofon atau model suara bermasalah: "
                              + type(exc).__name__ + ": " + str(exc))
        finally:
            self.finished.emit()
