"""Mobius: fully local file transformation engine. No network requests."""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

import fitz
from PIL import Image, ImageOps

PDF = {'.pdf'}
WORD = {'.docx', '.doc'}
IMAGES = {'.jpg', '.jpeg', '.png', '.webp', '.bmp', '.tif', '.tiff'}

@dataclass(frozen=True)
class Operation:
    key: str
    label: str
    subtitle: str
    extensions: frozenset[str]
    multiple: bool = True

OPERATIONS = [
    Operation('image_pdf', 'Gambar → PDF', 'JPG, PNG, WEBP', frozenset(IMAGES)),
    Operation('pdf_image', 'PDF → Gambar', 'Setiap halaman', frozenset(PDF)),
    Operation('word_pdf', 'Word → PDF', 'DOCX & DOC', frozenset(WORD)),
    Operation('pdf_word', 'PDF → Word', 'Dokumen DOCX', frozenset(PDF)),
    Operation('merge_pdf', 'Gabung PDF', '2+ file sekaligus', frozenset(PDF)),
    Operation('split_pdf', 'Pisah PDF', 'Per halaman', frozenset(PDF)),
    Operation('compress_pdf', 'Kompres PDF', 'Optimasi tanpa ubah gambar', frozenset(PDF)),
    Operation('rotate_pdf', 'Putar PDF', '90° searah jarum jam', frozenset(PDF)),
    Operation('convert_image', 'Ubah Format', 'PNG, JPG, WEBP', frozenset(IMAGES)),
]
BY_KEY = {op.key: op for op in OPERATIONS}

@dataclass
class Result:
    files: list[Path] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def supported(paths: list[Path], operation: str) -> bool:
    spec = BY_KEY[operation]
    return (bool(paths)
            and (operation != 'merge_pdf' or len(paths) >= 2)
            and all(p.suffix.lower() in spec.extensions and p.is_file() for p in paths))


def available_path(folder: Path, name: str) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    root = Path(name)
    candidate = folder / name
    i = 2
    while candidate.exists():
        candidate = folder / f'{root.stem}_{i}{root.suffix}'
        i += 1
    return candidate


def available_dir(folder: Path, name: str) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    candidate = folder / name
    i = 2
    while candidate.exists():
        candidate = folder / f'{name}_{i}'
        i += 1
    candidate.mkdir()
    return candidate


def _open_pdf(path: Path):
    doc = fitz.open(str(path))
    if doc.needs_pass:
        doc.close()
        raise ValueError(f'PDF terlindungi kata sandi: {path.name}')
    return doc


def _word_to_pdf_with_word(src: Path, dst: Path) -> bool:
    if sys.platform != 'win32':
        return False
    try:
        import win32com.client
    except ImportError:
        return False
    word = None
    doc = None
    try:
        word = win32com.client.DispatchEx('Word.Application')
        word.Visible = False
        word.DisplayAlerts = 0
        word.AutomationSecurity = 3  # Disable document macros while converting.
        doc = word.Documents.Open(str(src.resolve()), ReadOnly=True, AddToRecentFiles=False)
        doc.ExportAsFixedFormat(str(dst.resolve()), 17)  # wdExportFormatPDF
        return dst.is_file()
    except Exception:
        return False
    finally:
        if doc is not None:
            try: doc.Close(False)
            except Exception: pass
        if word is not None:
            try: word.Quit()
            except Exception: pass


def _soffice_binary() -> str | None:
    found = shutil.which('soffice') or shutil.which('libreoffice')
    if found:
        return found
    if sys.platform == 'win32':
        for var in ('PROGRAMFILES', 'PROGRAMFILES(X86)'):
            base = os.environ.get(var)
            if base:
                app = Path(base) / 'LibreOffice' / 'program' / 'soffice.exe'
                if app.is_file():
                    return str(app)
    return None


def _word_to_pdf_with_libreoffice(src: Path, dst: Path) -> bool:
    executable = _soffice_binary()
    if not executable:
        return False
    import tempfile
    with tempfile.TemporaryDirectory(prefix='mobius-lo-') as tmp:
        try:
            process = subprocess.run(
                [executable, '-env:UserInstallation=' + Path(tmp, 'profile').resolve().as_uri(),
                 '--headless', '--convert-to', 'pdf', '--outdir', tmp, str(src.resolve())],
                check=False, timeout=90, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            produced = Path(tmp) / (src.stem + '.pdf')
            if process.returncode == 0 and produced.exists():
                shutil.move(str(produced), dst)
                return True
        except (OSError, subprocess.TimeoutExpired):
            pass
    return False


def _word_to_pdf_basic(src: Path, dst: Path):
    """Fallback: editable text and basic tables, not a pixel-perfect Word renderer."""
    from docx import Document
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.enums import TA_LEFT
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.utils import simpleSplit
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    from xml.sax.saxutils import escape
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont

    font = 'Helvetica'
    candidates = [
        Path(os.environ.get('WINDIR', 'C:/Windows')) / 'Fonts' / 'arial.ttf',
        Path('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'),
    ]
    for p in candidates:
        if p.is_file():
            try:
                pdfmetrics.registerFont(TTFont('MobiusRegular', str(p)))
                font = 'MobiusRegular'
                break
            except Exception: pass
    styles = getSampleStyleSheet()
    regular = ParagraphStyle('MobiusBody', parent=styles['BodyText'], fontName=font, fontSize=10.3, leading=15, spaceAfter=8, alignment=TA_LEFT)
    heading = ParagraphStyle('MobiusHeading', parent=regular, fontSize=15, leading=21, spaceBefore=8)
    src_doc = Document(str(src))
    story = []
    for item in src_doc.element.body.iterchildren():
        if item.tag.endswith('}p'):
            from docx.text.paragraph import Paragraph as DocParagraph
            paragraph = DocParagraph(item, src_doc)
            content = escape(paragraph.text).replace('\n', '<br/>')
            if content.strip():
                story.append(Paragraph(content, heading if paragraph.style.name.lower().startswith('heading') else regular))
            else:
                story.append(Spacer(1, 6))
        elif item.tag.endswith('}tbl'):
            from docx.table import Table as DocTable
            table = DocTable(item, src_doc)
            rows = [[Paragraph(escape(cell.text).replace('\n','<br/>'), regular) for cell in row.cells] for row in table.rows]
            if rows:
                width = 490 / max(len(row) for row in rows)
                t = Table(rows, colWidths=[width] * max(len(row) for row in rows), hAlign='LEFT', repeatRows=1)
                t.setStyle(TableStyle([('GRID', (0, 0), (-1, -1), .4, colors.HexColor('#b8bcc8')),
                                       ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                                       ('PADDING', (0, 0), (-1, -1), 6)]))
                story.append(t)
                story.append(Spacer(1, 12))
    if not story:
        story = [Paragraph('(Dokumen kosong atau berisi elemen yang tidak didukung mode dasar.)', regular)]
    pdf = SimpleDocTemplate(str(dst), pagesize=A4, leftMargin=51, rightMargin=51, topMargin=48, bottomMargin=48)
    pdf.build(story)


def _pdf_to_docx(src: Path, dst: Path) -> bool:
    try:
        from pdf2docx import Converter
    except ImportError:
        return False
    converter = None
    try:
        converter = Converter(str(src))
        converter.convert(str(dst))
        return dst.is_file() and dst.stat().st_size > 0
    except Exception:
        if dst.exists():
            dst.unlink()
        return False
    finally:
        if converter is not None:
            converter.close()


def _pdf_to_docx_basic(src: Path, dst: Path):
    from docx import Document
    docx = Document()
    with _open_pdf(src) as pdf:
        for i, page in enumerate(pdf):
            if i:
                docx.add_page_break()
            blocks = sorted((b for b in page.get_text('blocks') if len(b) >= 7 and b[6] == 0), key=lambda b: (round(b[1] / 8), b[0]))
            for b in blocks:
                for para in b[4].split('\n'):
                    if para.strip():
                        docx.add_paragraph(para.strip())
    docx.save(str(dst))


def convert(operation: str, paths: list[Path | str], output: Path | str,
            image_format: str = 'PNG', report: Callable[[str], None] | None = None) -> Result:
    if operation not in BY_KEY:
        raise ValueError('Fitur tidak dikenal.')
    paths = [Path(p).expanduser().resolve() for p in paths]
    output = Path(output).expanduser()
    if not supported(paths, operation):
        raise ValueError('Format atau jumlah file tidak sesuai untuk alat ini.')
    output.mkdir(parents=True, exist_ok=True)
    image_format = image_format.upper().replace('JPEG', 'JPG')
    if image_format not in ('PNG', 'JPG', 'WEBP'):
        raise ValueError('Format gambar harus PNG, JPG, atau WEBP.')
    result = Result()
    def log(msg: str):
        if report: report(msg)

    if operation == 'image_pdf' and len(paths) > 1:
        # Like iLovePDF: several images become ONE multipage PDF in drop order.
        dest = available_path(output, 'Mobius_Gambar_Gabungan.pdf')
        pages = []
        try:
            for index, src in enumerate(paths):
                log(f'Menambahkan gambar {index + 1}/{len(paths)}…')
                with Image.open(src) as raw:
                    transformed = ImageOps.exif_transpose(raw)
                    if transformed.mode in ('RGBA', 'LA') or 'transparency' in transformed.info:
                        rgba = transformed.convert('RGBA')
                        image = Image.new('RGB', rgba.size, 'white')
                        image.paste(rgba, mask=rgba.getchannel('A'))
                    else:
                        image = transformed.convert('RGB')
                    pages.append(image)
            pages[0].save(dest, 'PDF', save_all=True, append_images=pages[1:], resolution=100.0)
            result.files.append(dest)
        finally:
            for page in pages:
                page.close()
        return result

    if operation == 'merge_pdf':
        dest = available_path(output, 'Mobius_Gabungan.pdf')
        with fitz.open() as merged:
            for index, src in enumerate(paths):
                log(f'Menggabungkan {index + 1}/{len(paths)}…')
                with _open_pdf(src) as doc:
                    merged.insert_pdf(doc)
            merged.ez_save(str(dest))
        result.files.append(dest)
        return result

    for index, src in enumerate(paths):
        log(f'{BY_KEY[operation].label} • {index + 1}/{len(paths)}: {src.name}')
        if operation == 'image_pdf':
            dest = available_path(output, src.stem + '.pdf' if len(paths) == 1 else src.stem + '_gambar.pdf')
            with Image.open(src) as raw:
                img = ImageOps.exif_transpose(raw)
                if img.mode in ('RGBA', 'LA') or 'transparency' in img.info:
                    bg = Image.new('RGB', img.size, 'white')
                    rgba = img.convert('RGBA')
                    bg.paste(rgba, mask=rgba.getchannel('A'))
                    img = bg
                else:
                    img = img.convert('RGB')
                img.save(dest, 'PDF', resolution=100.0)
            result.files.append(dest)
        elif operation == 'pdf_image':
            destdir = available_dir(output, src.stem + '_halaman')
            ext = '.jpg' if image_format == 'JPG' else '.' + image_format.lower()
            with _open_pdf(src) as doc:
                for page_no, page in enumerate(doc, 1):
                    pix = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
                    dest = destdir / f'halaman_{page_no:03d}{ext}'
                    if image_format == 'WEBP':
                        from io import BytesIO
                        with Image.open(BytesIO(pix.tobytes('png'))) as image:
                            image.save(dest, 'WEBP', quality=90)
                    else:
                        pix.save(str(dest), jpg_quality=90)
                    result.files.append(dest)
        elif operation == 'word_pdf':
            dest = available_path(output, src.stem + '.pdf')
            if not (_word_to_pdf_with_word(src, dest) or _word_to_pdf_with_libreoffice(src, dest)):
                if src.suffix.lower() == '.doc':
                    raise RuntimeError('File .DOC membutuhkan Microsoft Word atau LibreOffice terpasang.')
                _word_to_pdf_basic(src, dest)
                result.warnings.append(f'{src.name}: memakai mode dasar; tampilan bisa berbeda dari dokumen Word. Untuk hasil lebih setia gunakan Microsoft Word atau LibreOffice.')
            result.files.append(dest)
        elif operation == 'pdf_word':
            dest = available_path(output, src.stem + '.docx')
            if not _pdf_to_docx(src, dest):
                _pdf_to_docx_basic(src, dest)
                result.warnings.append(f'{src.name}: memakai ekstraksi teks dasar; layout dan gambar mungkin tidak ikut. Install pdf2docx untuk hasil lebih baik.')
            result.files.append(dest)
        elif operation == 'split_pdf':
            destdir = available_dir(output, src.stem + '_split')
            with _open_pdf(src) as pdf:
                for page_no in range(len(pdf)):
                    dest = destdir / f'{src.stem}_halaman_{page_no + 1:03d}.pdf'
                    with fitz.open() as one:
                        one.insert_pdf(pdf, from_page=page_no, to_page=page_no)
                        one.ez_save(str(dest))
                    result.files.append(dest)
        elif operation == 'compress_pdf':
            dest = available_path(output, src.stem + '_compressed.pdf')
            with _open_pdf(src) as doc:
                doc.ez_save(str(dest))
            if dest.stat().st_size >= src.stat().st_size:
                shutil.copy2(src, dest)
                result.warnings.append(f'{src.name}: sudah optimal; ukuran tidak berkurang.')
            result.files.append(dest)
        elif operation == 'rotate_pdf':
            dest = available_path(output, src.stem + '_rotated.pdf')
            with _open_pdf(src) as doc:
                for page in doc:
                    page.set_rotation((page.rotation + 90) % 360)
                doc.ez_save(str(dest))
            result.files.append(dest)
        elif operation == 'convert_image':
            ext = '.jpg' if image_format == 'JPG' else '.' + image_format.lower()
            dest = available_path(output, src.stem + '_mobius' + ext)
            with Image.open(src) as raw:
                image = ImageOps.exif_transpose(raw)
                if image_format == 'JPG':
                    if image.mode in ('RGBA', 'LA') or 'transparency' in image.info:
                        bg = Image.new('RGB', image.size, 'white')
                        rgba = image.convert('RGBA')
                        bg.paste(rgba, mask=rgba.getchannel('A'))
                        image = bg
                    else:
                        image = image.convert('RGB')
                    image.save(dest, 'JPEG', quality=92, optimize=True)
                elif image_format == 'PNG':
                    image.save(dest, 'PNG', optimize=True)
                else:
                    image.save(dest, 'WEBP', quality=90)
            result.files.append(dest)
    return result
