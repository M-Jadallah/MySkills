"""Render every PDF page to an inspection PNG, closing native handles per page."""
import argparse
import json
from pathlib import Path
import pypdfium2 as pdfium


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--pdf', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--dpi', type=int, default=96)
    args = p.parse_args()
    if args.dpi < 72:
        p.error('Use at least 72 DPI; 96+ is recommended for visual review')
    args.out.mkdir(parents=True, exist_ok=True)
    info = []
    pdf = pdfium.PdfDocument(args.pdf)
    try:
        for i in range(len(pdf)):
            page = pdf[i]
            try:
                bitmap = page.render(scale=args.dpi / 72)
                try:
                    image = bitmap.to_pil()
                    path = args.out / f'page-{i + 1}.png'
                    image.save(path)
                    info.append({'page': i + 1, 'path': str(path.resolve()), 'size': list(image.size), 'visually_reviewed': False})
                    image.close()
                finally:
                    bitmap.close()
            finally:
                page.close()
    finally:
        pdf.close()
    (args.out / 'pages.json').write_text(json.dumps({'source_pdf': str(args.pdf.resolve()), 'dpi': args.dpi, 'pages': info}, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'pages': len(info), 'out': str(args.out.resolve()), 'visual_review_complete': False}))


if __name__ == '__main__':
    main()
