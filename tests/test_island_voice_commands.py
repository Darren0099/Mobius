"""Regression tests for hands-free music, lyrics, Pomodoro and hydration."""
import pytest

from mobius.assistant_core import parse_command
from mobius.voice_commands import should_handle_utterance
from mobius.local_ai import validate


@pytest.mark.parametrize("spoken,kind,action", [
    ("pause musik", "media", "pause"),
    ("lanjutkan lagu", "media", "play"),
    ("skip lagu berikutnya", "media", "next"),
    ("previous lagu", "media", "previous"),
    ("putar lagu berikutnya", "media", "next"),
    ("mulai fokus 25 menit", "focus", "start"),
    ("pause pomodoro", "focus", "pause"),
    ("reset timer", "focus", "reset"),
])
def test_supported_voice_shortcuts(spoken, kind, action):
    assert should_handle_utterance(spoken)
    intent = parse_command(spoken)
    assert intent.kind == kind
    assert intent.args['action'] == action


@pytest.mark.parametrize("spoken,ml", [
    ("catat minum 250 ml", 250),
    ("minum air 500 ml", 500),
    ("catat minum air", None),
])
def test_water_voice_commands(spoken, ml):
    assert should_handle_utterance(spoken)
    intent = parse_command(spoken)
    assert intent.kind == 'water'
    assert intent.args.get('ml') == ml


def test_quick_lyrics_open_command():
    intent = parse_command("tampilkan lirik")
    assert intent.kind == 'quick'
    assert intent.args['page'] == 'lyrics'


def test_unknown_media_action_not_executable():
    assert validate({"kind": "media", "args": {"action": "shell"}}).kind == 'error'
    assert validate({"kind": "focus", "args": {"action": "start", "minutes": 900}}).kind == 'error'
    assert validate({"kind": "water", "args": {"ml": 10000}}).kind == 'error'
