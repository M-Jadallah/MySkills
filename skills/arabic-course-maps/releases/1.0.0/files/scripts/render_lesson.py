"""Render DOCX using Word on Windows or LibreOffice, then PNGs for visual QA."""
from __future__ import annotations
import argparse
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path


def run(cmd, timeout=150):
    options = {'capture_output': True, 'text': True, 'timeout': timeout, 'errors': 'replace'}
    if os.name == 'nt':
        options['creationflags'] = subprocess.CREATE_NO_WINDOW
    p = subprocess.run(cmd, **options)
    if p.returncode:
        raise RuntimeError(p.stdout + '\n' + p.stderr)
    return p.stdout


def verify_pdf_font(pdf):
    from pypdf import PdfReader
    names = set()
    for page in PdfReader(pdf).pages:
        resources = page.get('/Resources', {})
        if hasattr(resources, 'get_object'):
            resources = resources.get_object()
        font_dict = resources.get('/Font', {})
        if hasattr(font_dict, 'get_object'):
            font_dict = font_dict.get_object()
        for font in font_dict.values():
            names.add(str(font.get_object().get('/BaseFont', '')))
    if not names or any('traditionalarabic' not in name.lower().replace(' ', '') for name in names):
        raise RuntimeError('The renderer substituted the required Traditional Arabic font: '+', '.join(sorted(names)))
    return sorted(names)


def render(source, dest, engine='auto'):
    if engine == 'word' and os.name != 'nt':
        raise RuntimeError('The Word rendering adapter requires Windows')
    dest.mkdir(parents=True, exist_ok=True)
    pdf = dest/(source.stem+'.pdf')
    pdf.unlink(missing_ok=True)
    errors = []
    used = None
    if os.name == 'nt' and engine in ('auto', 'word'):
        try:
            run(['powershell.exe', '-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass', '-STA', '-File', str(Path(__file__).with_name('render_word.ps1')), '-InputDoc', str(source), '-PdfOut', str(pdf)])
            verify_pdf_font(pdf)
            used = 'Microsoft Word'
        except Exception as exc:
            errors.append('Word: ' + str(exc))
            pdf.unlink(missing_ok=True)
            if engine == 'word':
                raise
    if used is None:
        soffice = shutil.which('soffice') or shutil.which('soffice.exe')
        if not soffice and os.name == 'nt':
            candidate = Path(os.environ.get('ProgramFiles', 'C:/Program Files'))/'LibreOffice/program/soffice.exe'
            if candidate.is_file():
                soffice = str(candidate)
        if not soffice:
            raise RuntimeError('No DOCX renderer available. ' + '; '.join(errors))
        with tempfile.TemporaryDirectory(prefix='lesson-lo-', dir=dest) as profile:
            run([soffice, '-env:UserInstallation='+Path(profile).as_uri(), '--headless', '--convert-to', 'pdf', '--outdir', str(dest), str(source)])
        used = 'LibreOffice'
    if not pdf.is_file() or not pdf.stat().st_size:
        raise RuntimeError('Renderer did not produce a PDF')
    fonts = verify_pdf_font(pdf)
    for previous in dest.glob('page-*.png'):
        if previous.stem.removeprefix('page-').isdigit():
            previous.unlink()
    try:
        import pypdfium2 as pdfium
        handle = pdfium.PdfDocument(pdf)
        count = len(handle)
        for i in range(count):
            page = handle[i]
            bitmap = page.render(scale=1.8)
            bitmap.to_pil().save(dest/f'page-{i+1}.png')
            bitmap.close()
            page.close()
        handle.close()
    except ImportError:
        from pdf2image import convert_from_path
        pages = convert_from_path(str(pdf), dpi=140)
        count = len(pages)
        for i, page in enumerate(pages):
            page.save(dest/f'page-{i+1}.png')
    report = {'engine': used, 'page_count': count, 'pdf': str(pdf), 'verified_fonts': fonts, 'prior_engine_errors': errors}
    (dest/'render-report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('docx', type=Path)
    parser.add_argument('--output-dir', required=True, type=Path)
    parser.add_argument('--engine', choices=['auto', 'word', 'libreoffice'], default='auto')
    args = parser.parse_args()
    render(args.docx.resolve(), args.output_dir.resolve(), args.engine)
