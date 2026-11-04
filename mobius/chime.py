"""Short original two-tone chime for focus transitions. No audio downloads."""
from __future__ import annotations

import io
import math
import struct
import sys
import threading
import wave


def chime_wav() -> bytes:
    rate = 22050
    duration = 0.52
    count = int(rate * duration)
    samples = bytearray()
    for i in range(count):
        t = i / rate
        attack = min(1.0, t / 0.028)
        release = max(0.0, (duration - t) / 0.22)
        envelope = min(attack, release)
        # Original, gentle major interval. Peak amplitude 14% of full scale.
        tone = .68 * math.sin(2 * math.pi * 587.33 * t)
        tone += .32 * math.sin(2 * math.pi * 783.99 * t)
        value = int(32767 * 0.14 * envelope * tone)
        samples.extend(struct.pack("<h", value))
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(rate)
        output.writeframes(bytes(samples))
    return buffer.getvalue()


def play_soft_chime():
    if sys.platform != "win32":
        return
    def play():
        try:
            import winsound
            winsound.PlaySound(chime_wav(), winsound.SND_MEMORY | winsound.SND_SYNC)
        except (OSError, RuntimeError):
            pass
    threading.Thread(target=play, name="MobiusChime", daemon=True).start()
