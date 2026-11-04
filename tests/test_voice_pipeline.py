"""Regression tests for hands-free commands and English feedback.

Hardware microphone and actual Windows SAPI audio require manual testing.
"""
from types import SimpleNamespace
from urllib.parse import parse_qs, urlparse

import pytest

from mobius.assistant_core import parse_command, execute
from mobius.voice_commands import should_handle_utterance
from mobius.voice_feedback import english_confirmation
from mobius.voice_gate import AdaptiveSpeechGate


@pytest.mark.parametrize("spoken, expected", [
    ("buka kalkulator", ["kalkulator"]),
    ("tolong buka kalkulator", ["kalkulator"]),
    ("bukain dong kalkulator", ["kalkulator"]),
    ("bukain kalkulator dong", ["kalkulator"]),
    ("Mobius buka kalkulator", ["kalkulator"]),
    ("buka notepad dan kalkulator", ["notepad", "kalkulator"]),
])
def test_application_voice_intents_without_wake_word(spoken, expected):
    assert should_handle_utterance(spoken)
    intent = parse_command(spoken)
    assert intent.kind == 'apps'
    assert intent.args['apps'] == expected


@pytest.mark.parametrize("spoken, query", [
    ("cari resep rendang di browser", "resep rendang"),
    ("carikan resep nasi goreng di Google", "resep nasi goreng"),
    ("cariin resep sate ayam dong", "resep sate ayam"),
    ("buka browser dan cari cara install Python", "cara install python"),
    ("Mobius tolong cari resep A di browser", "resep a"),
])
def test_search_voice_intents_without_wake_word(spoken, query):
    assert should_handle_utterance(spoken)
    intent = parse_command(spoken)
    assert intent.kind == 'search'
    assert intent.args['query'] == query


@pytest.mark.parametrize("spoken", [
    "jangan buka kalkulator",
    "nggak usah buka kalkulator",
    "sedang bermain game",
    "percakapan dari televisi",
    "lampu menyala",
])
def test_noncommands_do_not_trigger_actions(spoken):
    assert not should_handle_utterance(spoken)


def test_quieter_microphone_profile_is_more_sensitive():
    assert AdaptiveSpeechGate("high").is_speech(0.004)
    assert not AdaptiveSpeechGate("low").is_speech(0.004)


def test_calculator_executed_as_windows_program(monkeypatch):
    from mobius import assistant_core
    started = []
    monkeypatch.setattr(assistant_core.sys, "platform", "win32")
    monkeypatch.setattr(assistant_core.subprocess, "Popen",
                        lambda args, **kwargs: started.append(args))
    intent = parse_command("buka kalkulator")
    result = execute(intent)
    assert started == [["calc.exe"]]
    assert result == "Aplikasi dibuka: kalkulator"
    assert english_confirmation(intent, result) == "Okay, calculator is now open."


def test_search_opens_url_and_english_tts_only_on_success(monkeypatch):
    from mobius import assistant_core
    opened = []
    monkeypatch.setattr(assistant_core.webbrowser, "open",
                        lambda url: opened.append(url) or True)
    intent = parse_command("cari resep nasi goreng di browser")
    result = execute(intent)
    assert urlparse(opened[0]).hostname == "www.google.com"
    assert parse_qs(urlparse(opened[0]).query)["q"] == ["resep nasi goreng"]
    assert result.startswith("Pencarian dibuka")
    assert english_confirmation(intent, result) == (
        "Okay, I opened the browser search for recipes for nasi goreng."
    )

    monkeypatch.setattr(assistant_core.webbrowser, "open", lambda url: False)
    failed = execute(intent)
    assert failed.startswith("Tidak dapat")
    assert english_confirmation(intent, failed) is None


def test_english_feedback_never_claims_success_on_failure():
    app = SimpleNamespace(kind="apps", args={"apps": ["kalkulator"]})
    assert english_confirmation(app, 'Aplikasi “kalkulator” tidak ditemukan.') is None
    assert english_confirmation(SimpleNamespace(kind="search", args={"query":"rendang"}),
                                "Tidak dapat membuka pencarian di browser.") is None


def test_ui_receives_voice_without_mobius_and_suppresses_speaker_echo():
    from pathlib import Path
    source = (Path(__file__).resolve().parents[1] / "mobius" / "ui.py").read_text(encoding="utf-8")
    assert "self.on_phrase(phrase, require_wake=False)" in source
    assert "suppress_event=self.feedback.playing" in source
    assert "self.feedback.speak(spoken)" in source
