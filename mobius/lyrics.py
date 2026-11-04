"""Timed lyrics: local LRC and opt-in community lookup.

No lyrics bundled or scraped. A lookup sends song metadata to LRCLIB only
when the user explicitly clicks Find lyrics; local LRC works offline.
"""
from __future__ import annotations

import json
import re
from bisect import bisect_right
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen


LRC_TIME = re.compile(r"\[(\d{1,3}):([0-5]\d)(?:\.(\d{1,3}))?\]")


def parse_lrc(content: str) -> list[tuple[float, str]]:
    lines = []
    for raw in content.splitlines():
        matches = list(LRC_TIME.finditer(raw))
        if not matches:
            continue
        lyric = LRC_TIME.sub("", raw).strip()
        if not lyric:
            continue
        for match in matches:
            fraction = (match.group(3) or "").ljust(3, "0")[:3]
            position = int(match.group(1)) * 60 + int(match.group(2)) + int(fraction) / 1000
            lines.append((position, lyric))
    return sorted(lines, key=lambda item: item[0])


def active_line(lines: list[tuple[float, str]], playback_seconds: float) -> int:
    if not lines:
        return -1
    return bisect_right([pos for pos, _ in lines], max(0, playback_seconds)) - 1


def load_lrc(path: Path) -> list[tuple[float, str]]:
    if path.suffix.lower() != ".lrc" or path.stat().st_size > 2_000_000:
        raise ValueError("Pilih file .lrc maksimal 2 MB")
    return parse_lrc(path.read_text(encoding="utf-8-sig", errors="replace"))


def search_lrclib(title: str, artist: str, seconds: float = 0) -> list[tuple[float, str]]:
    """Opt-in network access; title/artist sent, no audio and no account token."""
    if not title.strip() or len(title) > 180 or len(artist) > 180:
        return []
    parameters = urlencode({"track_name": title.strip(), "artist_name": artist.strip()})
    url = "https://lrclib.net/api/search?" + parameters
    req = Request(url, headers={"User-Agent": "Mobius/0.7 (https://github.com/Darren0099/Mobius)",
                                 "Accept": "application/json"})
    with urlopen(req, timeout=9) as response:
        data = json.loads(response.read(750000).decode("utf-8"))
    if not isinstance(data, list):
        return []
    for record in data[:12]:
        if not isinstance(record, dict):
            continue
        if record.get("trackName", "").casefold() != title.casefold():
            continue
        record_artist = str(record.get("artistName", "")).casefold()
        if artist and artist.casefold() not in record_artist and record_artist not in artist.casefold():
            continue
        duration = record.get("duration")
        if seconds > 0 and duration and abs(float(duration) - seconds) > 5:
            continue
        synced = record.get("syncedLyrics")
        if isinstance(synced, str) and synced:
            return parse_lrc(synced)
    return []
