"""Local, bounded command parser and Windows action runner for Mobius.

No network/LLM/shell execution of dictated strings. Internet is accessed only
when the user explicitly asks their *browser* to open a search/web page.
"""
from __future__ import annotations

import os
import random
import re
import shutil
import subprocess
import sys
import webbrowser
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import quote_plus

from .engine import convert, supported

# Only these known application aliases can be launched. Never pass user text
# directly to cmd.exe, PowerShell, or subprocess shell=True.
APP_NAMES = {
    'notepad': ('notepad.exe',), 'catatan': ('notepad.exe',),
    'kalkulator': ('calc.exe',), 'calculator': ('calc.exe',),
    'file explorer': ('explorer.exe',), 'explorer': ('explorer.exe',),
    'paint': ('mspaint.exe',), 'terminal': ('wt.exe',),
    'command prompt': ('cmd.exe',),
    'vscode': ('Code.exe',), 'vs code': ('Code.exe',), 'visual studio code': ('Code.exe',),
    'chrome': ('chrome.exe',), 'google chrome': ('chrome.exe',),
    'edge': ('msedge.exe',), 'microsoft edge': ('msedge.exe',),
    'firefox': ('firefox.exe',), 'spotify': ('Spotify.exe',),
    'discord': ('Discord.exe',),
}

IMAGE_TO_PDF = r'(?:gambar|foto|image|img)\s+(?:ke|to|jadi|menjadi)\s+pdf'
PDF_TO_IMAGE = r'pdf\s+(?:ke|to|jadi|menjadi)\s+(?:gambar|foto|image|img|jpg|png)'
PDF_TO_WORD = r'pdf\s+(?:ke|to|jadi|menjadi)\s+(?:word|docx)'
WORD_TO_PDF = r'(?:word|docx|doc)\s+(?:ke|to|jadi|menjadi)\s+pdf'
CONVERSION_PATTERNS = (
    ('image_pdf', IMAGE_TO_PDF), ('pdf_image', PDF_TO_IMAGE),
    ('pdf_word', PDF_TO_WORD), ('word_pdf', WORD_TO_PDF),
)

@dataclass
class Intent:
    kind: str
    detail: str = ''
    args: dict = field(default_factory=dict)
    dangerous: bool = False


def clean(text: str) -> str:
    return re.sub(r'\s+', ' ', text.lower().strip()).strip(' .,!?')


def parse_command(text: str) -> Intent:
    s = clean(text)
    s = re.sub(r'^(?:hei|hey|hai|halo|oke|ok)?\s*mobius\b[,:]?\s*', '', s).strip()
    s = re.sub(r'^(?:tolong|bantu|silakan|coba)\s+', '', s)
    if not s:
        return Intent('help', 'Katakan perintah setelah “Mobius”.')
    if re.search(r'\b(?:batalkan|batal|cancel|abort)\b.*\b(?:shutdown|mati|matikan|restart)\b', s) or re.search(r'\b(?:shutdown|mati|matikan)\b.*\b(?:batal|cancel)\b', s):
        return Intent('cancel_shutdown', 'Batalkan jadwal shutdown Windows.')
    if re.search(r'\b(?:matikan|shutdown|turn off)\b.*\b(?:laptop|komputer|pc|windows)\b', s):
        match = re.search(r'(\d+)\s*(menit|minute|jam|hour|detik|second)', s)
        if not match:
            return Intent('shutdown', 'Matikan laptop sekarang?', {'seconds': 0}, True)
        n = int(match.group(1))
        scale = {'menit': 60, 'minute': 60, 'jam': 3600, 'hour': 3600, 'detik': 1, 'second': 1}[match.group(2)]
        seconds = n * scale
        if not 1 <= seconds <= 86400:
            return Intent('error', 'Waktu shutdown harus 1 detik sampai 24 jam.')
        return Intent('shutdown', f'Jadwalkan shutdown dalam {n} {match.group(2)}?', {'seconds': seconds}, True)
    if re.search(r'\b(?:putar|play|mainkan)\b.*\b(?:musik|lagu|music)\b', s):
        return Intent('music', 'Putar lagu lokal secara acak.')
    if re.search(r'\b(?:cari|search|telusuri)\b', s) and not re.search(r'\b(?:file|berkas|dokumen|pdf)\b', s):
        m = re.search(r'\b(?:cari|search|telusuri)\b\s+(?:di\s+(?:browser|google|internet)\s+)?(?:tentang\s+)?(.+)', s)
        if m and m.group(1).strip():
            query = m.group(1).strip()
            return Intent('search', f'Cari “{query}” di browser?', {'query': query})
    if re.search(r'\b(?:buka|open|jalankan)\b.*\b(?:browser|peramban)\b', s):
        rest = re.search(r'\b(?:cari|search|telusuri)\b\s+(.+)', s)
        if rest:
            q = rest.group(1)
            return Intent('search', f'Cari “{q}” di browser?', {'query': q})
        return Intent('browser', 'Buka browser bawaan.')
    # The form "ubah PDF nama menjadi img" includes the filename BETWEEN
    # source and target, so recognise the suffix direction independently.
    if re.search(r'\b(?:ubah|konversi|convert|jadikan)\b', s):
        for kind, pattern in CONVERSION_PATTERNS:
            if re.search(pattern, s):
                name = _filename(s)
                return Intent('convert', f'Konversi {kind.replace("_", " → ")}: {name or "pilih file"}', {'operation': kind, 'filename': name})
        m = re.search(r'\bpdf\b\s+(.+?)\s+(?:menjadi|ke|to|jadi)\s+(?:img|gambar|foto|image|jpg|png)\b', s)
        if m:
            return Intent('convert', f'Ubah PDF “{m.group(1)}” menjadi gambar.', {'operation': 'pdf_image', 'filename': m.group(1)})
        m = re.search(r'\b(?:word|docx)\b\s+(.+?)\s+(?:menjadi|ke|to|jadi)\s+pdf\b', s)
        if m:
            return Intent('convert', f'Ubah Word “{m.group(1)}” menjadi PDF.', {'operation': 'word_pdf', 'filename': m.group(1)})
        m = re.search(r'\bpdf\b\s+(.+?)\s+(?:menjadi|ke|to|jadi)\s+(?:word|docx)\b', s)
        if m:
            return Intent('convert', f'Ubah PDF “{m.group(1)}” menjadi Word.', {'operation': 'pdf_word', 'filename': m.group(1)})
    if re.search(r'\b(?:buka|open|jalankan)\b', s):
        raw = re.sub(r'^.*?\b(?:buka|open|jalankan)\b\s+', '', s)
        raw = re.sub(r'^(?:aplikasi|app|program)\s+', '', raw)
        targets = [re.sub(r'^(?:aplikasi|app)\s+', '', x.strip()) for x in re.split(r'\s*(?:,|\bdan\b|\bserta\b)\s*', raw) if x.strip()]
        unknown = [x for x in targets if x not in APP_NAMES]
        if unknown:
            return Intent('error', 'Aplikasi belum dikenal: ' + ', '.join(unknown) + '. Tambahkan alias aplikasi di kode konfigurasi.')
        if targets:
            return Intent('apps', 'Buka aplikasi: ' + ', '.join(targets), {'apps': targets})
    return Intent('help', 'Aku belum memahami perintah. Coba “buka notepad”, “cari tutorial Python”, atau “ubah PDF laporan menjadi gambar”.')


def _filename(s: str) -> str:
    quoted = re.search(r'["“](.+?)["”]', s)
    if quoted:
        return quoted.group(1).strip()
    m = re.search(r'\b(?:bernama|nama file|file|dokumen)\s+(.+?)(?:\s+(?:menjadi|jadi|ke|to)\s+(?:pdf|gambar|image|img|word|docx|jpg|png))?$', s)
    return m.group(1).strip() if m else ''


def resolve_document(name: str, paths: list[Path] | None = None, folders: list[Path] | None = None) -> Path:
    """Resolve in safe user folders (nonrecursive) only. Reject ambiguous matches."""
    options = [p for p in (paths or []) if p.is_file()]
    if not name:
        if len(options) == 1:
            return options[0]
        raise FileNotFoundError('Seret satu file ke Mobius dahulu atau sebut nama file.')
    name = Path(name.strip().strip('"“”')).name.casefold()
    places = folders if folders is not None else [Path.home() / p for p in ('Documents', 'Downloads', 'Desktop')]
    candidates = list(options)
    for folder in places:
        if folder.exists():
            candidates.extend(p for p in folder.iterdir() if p.is_file())
    matches = {str(p.resolve()).casefold(): p for p in candidates if p.name.casefold() == name or p.stem.casefold() == name}
    if not matches:
        raise FileNotFoundError(f'File “{name}” tidak ditemukan di Documents, Downloads, Desktop atau file yang di-drop.')
    if len(matches) > 1:
        raise ValueError('Ada beberapa file bernama sama. Drop file yang dimaksud ke Mobius untuk memastikan.')
    return next(iter(matches.values()))


def execute(intent: Intent, *, dropped: list[Path] | None = None, output: Path | None = None) -> str:
    """Only execute a parsed, explicitly supported action. UI confirms dangerous ones."""
    if intent.kind in ('help', 'error'):
        return intent.detail
    if intent.kind == 'apps':
        if sys.platform != 'win32':
            return 'Membuka aplikasi Windows hanya tersedia ketika Mobius berjalan di Windows.'
        for app in intent.args['apps']:
            exe = APP_NAMES[app][0]
            try:
                subprocess.Popen([exe], shell=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except OSError:
                return f'Aplikasi “{app}” tidak ditemukan. Periksa apakah sudah terpasang dan terdaftar di PATH.'
        return 'Aplikasi dibuka: ' + ', '.join(intent.args['apps'])
    if intent.kind == 'browser':
        webbrowser.open('about:blank')
        return 'Browser dibuka.'
    if intent.kind == 'search':
        webbrowser.open('https://www.google.com/search?q=' + quote_plus(intent.args['query']))
        return 'Pencarian dibuka di browser. Membutuhkan internet untuk hasil pencarian.'
    if intent.kind == 'music':
        folder = Path.home() / 'Music'
        tracks = [p for p in folder.rglob('*') if p.is_file() and p.suffix.lower() in {'.mp3', '.wav', '.flac', '.m4a', '.ogg'}] if folder.exists() else []
        if not tracks:
            return 'Tidak ada lagu lokal di folder Music. Simpan file audio ke folder tersebut dahulu.'
        song = random.choice(tracks)
        if sys.platform == 'win32':
            os.startfile(str(song))
        else:
            subprocess.Popen(['xdg-open', str(song)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return 'Memutar musik acak: ' + song.name
    if intent.kind == 'convert':
        path = resolve_document(intent.args['filename'], dropped)
        operation = intent.args['operation']
        if not supported([path], operation):
            return f'Format {path.suffix} tidak cocok dengan konversi yang diminta.'
        result = convert(operation, [path], output or (Path.home() / 'Documents' / 'Mobius'))
        return f'Selesai: {len(result.files)} file disimpan. ' + ', '.join(p.name for p in result.files[:3])
    if intent.kind == 'shutdown':
        if sys.platform != 'win32':
            return 'Shutdown melalui Mobius hanya tersedia di Windows.'
        seconds = intent.args['seconds']
        subprocess.run(['shutdown.exe', '/s', '/t', str(seconds)], check=True, timeout=10)
        return f'Shutdown terjadwal dalam {seconds} detik. Ucapkan “Mobius batalkan shutdown” untuk membatalkan.'
    if intent.kind == 'cancel_shutdown':
        if sys.platform != 'win32':
            return 'Pembatalan shutdown tersedia di Windows.'
        result = subprocess.run(['shutdown.exe', '/a'], check=False, capture_output=True, timeout=10)
        return 'Shutdown berhasil dibatalkan.' if result.returncode == 0 else 'Tidak ada jadwal shutdown yang dapat dibatalkan.'
    return 'Perintah tidak tersedia.'
