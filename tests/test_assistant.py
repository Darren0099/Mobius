from pathlib import Path

import pytest
from mobius.assistant_core import parse_command, resolve_document, execute


def test_open_multiple_apps():
    intent = parse_command('Mobius tolong buka aplikasi notepad dan kalkulator')
    assert intent.kind == 'apps'
    assert intent.args['apps'] == ['notepad', 'kalkulator']


def test_browser_search_includes_words():
    intent = parse_command('mobius tolong buka browser dan cari cara install Python')
    assert intent.kind == 'search'
    assert intent.args['query'] == 'cara install python'


def test_shutdown_10_minutes_requires_confirmation():
    intent = parse_command('Mobius tolong matikan laptop dalam waktu 10 menit lagi')
    assert intent.kind == 'shutdown'
    assert intent.args['seconds'] == 600
    assert intent.dangerous


def test_cancel_shutdown():
    assert parse_command('mobius batalkan shutdown').kind == 'cancel_shutdown'


def test_pdf_to_img_natural_language():
    intent = parse_command('Mobius tolong ubah PDF laporan menjadi img')
    assert intent.kind == 'convert'
    assert intent.args == {'operation': 'pdf_image', 'filename': 'laporan'}


def test_music():
    assert parse_command('Mobius tolong putar musik acak').kind == 'music'


def test_no_shell_injection():
    intent = parse_command('buka notepad && del C:/Users')
    assert intent.kind == 'error'


def test_resolve_ambiguous_filename(tmp_path):
    first = tmp_path / 'a'
    second = tmp_path / 'b'
    first.mkdir(); second.mkdir()
    (first / 'laporan.pdf').write_bytes(b'pdf1')
    (second / 'laporan.pdf').write_bytes(b'pdf2')
    with pytest.raises(ValueError):
        resolve_document('laporan', folders=[first, second])
    assert resolve_document('laporan.pdf', folders=[first]).name == 'laporan.pdf'


def test_unknown_command_has_no_side_effects():
    assert 'belum' in execute(parse_command('format hard drive')).lower()
