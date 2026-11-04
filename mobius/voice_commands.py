"""Conservative command filtering for ambient, wake-word-free listening.

Without a wake word an always-on microphone may hear videos, TV and other
people. Only intentional-sounding imperatives/questions are dispatched.
"""
from __future__ import annotations

import re

STARTERS = frozenset({
    'buka', 'bukain', 'bukakan', 'open', 'jalankan', 'launch', 'nyalain',
    'nyalakan', 'cari', 'carikan', 'cariin', 'search', 'telusuri', 'googling',
    'putar', 'play', 'mainkan', 'ubah', 'konversi', 'convert', 'jadikan',
    'gabung', 'pisah', 'kompres', 'matikan', 'shutdown', 'batalkan', 'batal',
    'jelaskan', 'ceritakan', 'terangkan', 'tunjukkan', 'beritahu',
    'apa', 'apakah', 'bagaimana', 'gimana', 'kenapa', 'mengapa', 'siapa',
    'kapan', 'dimana', 'di', 'bisakah', 'bisa', 'pause', 'jeda',
    'stop', 'hentikan', 'lanjutkan', 'lanjut', 'resume', 'next',
    'previous', 'sebelumnya', 'skip', 'lewati', 'mulai', 'start',
    'aktifkan', 'reset', 'ulang', 'minum', 'catat', 'tambah', 'tampilkan',
    'lihat', 'show',
})
FILLERS = frozenset({'tolong', 'bantu', 'coba', 'please', 'dong', 'deh', 'hei', 'hey', 'halo', 'hai', 'oke', 'ok'})
NEGATIONS = ('jangan ', 'ga usah ', 'gak usah ', 'nggak usah ', 'tidak usah ', "don't ", 'do not ')


def should_handle_utterance(text: str) -> bool:
    """Whether an utterance is suitable for the command/AI interpreter."""
    if not text or len(text.strip()) < 5 or len(text) > 550:
        return False
    s = re.sub(r'\s+', ' ', re.sub(r'[^a-z0-9\s]', ' ', text.casefold())).strip()
    if not s:
        return False
    words = s.split()
    if 'mobius' in words[:2]:
        i = words.index('mobius')
        words = words[i + 1:]
        if not words:
            return False
    while words and words[0] in FILLERS:
        words.pop(0)
    if not words or len(words) < 2:
        return False
    phrase = ' '.join(words)
    if phrase.startswith(NEGATIONS):
        return False
    return words[0] in STARTERS


def normalized_utterance(text: str) -> str:
    return re.sub(r'\s+', ' ', re.sub(r'[^a-z0-9\s]', '', text.casefold())).strip()
