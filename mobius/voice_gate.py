"""Speech activity detector for local, hands-free Indonesian commands.

Operates on 100ms RMS samples; avoids the former hard-coded 0.016 cutoff.
It is not speech recognition: Whisper still decides whether audio is language.
"""
from __future__ import annotations

import math
import os

PROFILES = {
    "high": (0.0030, 2.0),
    "normal": (0.0045, 2.7),
    "low": (0.0070, 3.4),
}


class AdaptiveSpeechGate:
    """Update the measured noise floor only while waiting for speech."""

    def __init__(self, sensitivity: str | None = None):
        choice = (sensitivity or os.environ.get("MOBIUS_MIC_SENSITIVITY", "high")).lower()
        self.sensitivity = choice if choice in PROFILES else "high"
        self.min_rms, self.ratio = PROFILES[self.sensitivity]
        self.noise_floor = 0.0015

    def is_speech(self, rms: float, *, continuing: bool = False) -> bool:
        if not math.isfinite(rms) or rms < 0:
            return False
        multiplier = 1.35 if continuing else self.ratio
        threshold = max(self.min_rms * (0.65 if continuing else 1.0),
                        min(0.028, self.noise_floor * multiplier))
        heard = rms >= threshold
        if not continuing and not heard:
            # Learn typical room noise slowly; cap each contribution to avoid spikes.
            self.noise_floor = (0.94 * self.noise_floor
                                + 0.06 * min(rms, threshold))
        return heard
