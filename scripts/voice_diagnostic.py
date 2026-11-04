"""Five-second offline microphone/Whisper + English TTS self-test.

Runs ONLY after explicit user action. Does not launch Windows apps or store audio.
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    import numpy as np
    import sounddevice as sd
    from faster_whisper import WhisperModel

    from mobius.voice import microphone_input_config, audio_for_whisper, voice_model_dir
    from mobius.voice_commands import should_handle_utterance
    from mobius.assistant_core import parse_command
    from mobius.voice_feedback import SpeechFeedback

    print("=== MOBIUS OFFLINE MICROPHONE DIAGNOSTIC ===")
    print("Available input devices:")
    print(sd.query_devices())
    try:
        device, rate = microphone_input_config(sd)
    except Exception as exc:
        print(f"Microphone device error: {type(exc).__name__}: {exc}")
        print("Windows Settings > Privacy & security > Microphone: allow desktop app access.")
        return 2
    print(f"\nSelected input: {device or 'Windows default'}; sampling rate: {rate} Hz")
    print('Say: "buka kalkulator" or "cari resep rendang di browser"')
    print("Recording for 5 seconds. No application will be opened by this test.")
    try:
        raw = sd.rec(rate * 5, samplerate=rate, channels=1, dtype='float32', device=device)
        sd.wait()
    except Exception as exc:
        print(f"Recording error: {type(exc).__name__}: {exc}")
        return 3

    waveform = raw.ravel()
    rms = float(np.sqrt(np.mean(waveform * waveform)))
    peak = float(np.max(np.abs(waveform)))
    print(f"Audio level RMS: {rms:.5f}; peak: {peak:.5f}")
    if rms < 0.002:
        print("Warning: very quiet microphone signal. Check input device, distance and input level.")

    print("Transcribing with locally cached Whisper model...")
    try:
        model = WhisperModel(os.environ.get('MOBIUS_VOICE_MODEL', 'base'),
                             device='cpu', compute_type='int8',
                             download_root=str(voice_model_dir()), local_files_only=True)
        samples = audio_for_whisper(waveform, rate, np)
        segments, _ = model.transcribe(
            samples, language='id', beam_size=3, vad_filter=False,
            condition_on_previous_text=False, no_speech_threshold=0.65)
        transcript = " ".join(s.text for s in segments).strip()
    except Exception as exc:
        print(f"Whisper error: {type(exc).__name__}: {exc}")
        return 4
    print("Whisper heard:", repr(transcript))
    print("Directed command accepted:", should_handle_utterance(transcript))
    parsed = parse_command(transcript)
    print("Detected intent:", parsed.kind, parsed.args)
    print("NOTE: No computer action is executed in diagnostic mode.")

    print("\nTesting English voice feedback via local Windows SAPI...")
    speaker = SpeechFeedback()
    speaker.speak("Okay. Your microphone diagnostic is complete.")
    time.sleep(4.0)
    speaker.stop()
    print("Finished. If no voice was heard, check Windows output volume and English speech voices.")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
