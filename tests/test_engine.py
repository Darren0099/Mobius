import os
from pathlib import Path

import fitz
import pytest
from PIL import Image
from docx import Document
from mobius.engine import convert, supported

@pytest.fixture
def samples(tmp_path):
    image = tmp_path / 'test.png'
    Image.new('RGBA', (180, 125), (53, 145, 220, 190)).save(image)
    pdf1 = tmp_path / 'first.pdf'
    with fitz.open() as d:
        a = d.new_page()
        a.insert_text((75, 92), 'Mobius TEST ONE')
        b = d.new_page()
        b.insert_text((75, 92), 'PAGE TWO')
        d.save(str(pdf1))
    pdf2 = tmp_path / 'second.pdf'
    with fitz.open() as d:
        p = d.new_page()
        p.insert_text((75, 92), 'ANOTHER FILE')
        d.save(str(pdf2))
    word = tmp_path / 'sample.docx'
    document = Document()
    document.add_heading('Mobius Demo', level=1)
    document.add_paragraph('A paragraph here.')
    document.add_table(rows=2, cols=2)
    document.save(word)
    return image, pdf1, pdf2, word


def test_image_to_pdf(tmp_path, samples):
    result = convert('image_pdf', [samples[0]], tmp_path / 'results')
    with fitz.open(str(result.files[0])) as pdf:
        assert len(pdf) == 1
    assert samples[0].exists()


def test_pdf_to_images(tmp_path, samples):
    result = convert('pdf_image', [samples[1]], tmp_path / 'results', image_format='JPG')
    assert len(result.files) == 2
    assert all(f.suffix == '.jpg' for f in result.files)


def test_merge_split_rotate_compress(tmp_path, samples):
    pdf1, pdf2 = samples[1:3]
    merged = convert('merge_pdf', [pdf1, pdf2], tmp_path / 'results')
    with fitz.open(str(merged.files[0])) as d:
        assert len(d) == 3
    split = convert('split_pdf', [pdf1], tmp_path / 'results')
    assert len(split.files) == 2
    rotated = convert('rotate_pdf', [pdf1], tmp_path / 'results')
    with fitz.open(str(rotated.files[0])) as d:
        assert d[0].rotation == 90
    compressed = convert('compress_pdf', [pdf1], tmp_path / 'results')
    assert compressed.files[0].exists()
    assert compressed.files[0].stat().st_size <= pdf1.stat().st_size


def test_image_conversion(tmp_path, samples):
    result = convert('convert_image', [samples[0]], tmp_path / 'results', image_format='WEBP')
    with Image.open(result.files[0]) as image:
        assert image.format == 'WEBP'
    result = convert('convert_image', [samples[0]], tmp_path / 'results', image_format='JPG')
    with Image.open(result.files[0]) as image:
        assert image.mode == 'RGB'


def test_word_pdf_and_pdf_word(tmp_path, samples):
    word_to_pdf = convert('word_pdf', [samples[3]], tmp_path / 'results')
    assert word_to_pdf.files[0].exists()
    with fitz.open(str(word_to_pdf.files[0])) as d:
        assert 'Mobius Demo' in d[0].get_text()
    pdf_to_word = convert('pdf_word', [samples[1]], tmp_path / 'results')
    doc = Document(pdf_to_word.files[0])
    assert 'Mobius TEST ONE' in '\n'.join(p.text for p in doc.paragraphs)


def test_validation_and_unique_paths(tmp_path, samples):
    assert not supported([samples[1]], 'merge_pdf')
    assert not supported([samples[0]], 'pdf_word')
    a = convert('image_pdf', [samples[0]], tmp_path / 'results')
    b = convert('image_pdf', [samples[0]], tmp_path / 'results')
    assert a.files[0] != b.files[0]
    with pytest.raises(ValueError):
        convert('word_pdf', [samples[0]], tmp_path / 'results')


def test_multiple_images_one_pdf(tmp_path, samples):
    second = tmp_path / 'second.png'
    Image.new('RGB', (65, 32), 'purple').save(second)
    result = convert('image_pdf', [samples[0], second], tmp_path / 'results')
    assert len(result.files) == 1
    with fitz.open(str(result.files[0])) as doc:
        assert len(doc) == 2
