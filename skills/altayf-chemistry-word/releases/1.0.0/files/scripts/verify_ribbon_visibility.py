"""Detect ribbon PNGs clipped by Word line-height despite their OOXML presence."""
import argparse
from pathlib import Path

import fitz
from PIL import Image
from common import read_json, write_json


def verify(pdf, render_dir, cards):
    expected = sum(bool(card.get('visible_ribbon_expected')) for card in read_json(cards))
    visible = 0
    found = []
    document = fitz.open(pdf)
    try:
        for page_index, page in enumerate(document):
            png = Path(render_dir) / f'page-{page_index + 1:03d}.png'
            im = Image.open(png).convert('RGB')
            sx, sy = im.width / page.rect.width, im.height / page.rect.height
            for info in page.get_image_info():
                width, height = info['width'], info['height']
                if not (height and 2.7 <= width / height <= 3.3):
                    continue
                x0, y0, x1, y1 = info['bbox']
                if not (100 <= x1 - x0 <= 125 and 30 <= y1 - y0 <= 45):
                    continue
                crop = im.crop((round(x0 * sx), round(y0 * sy), round(x1 * sx), round(y1 * sy)))
                navy = sum(1 for r, g, b in crop.getdata() if r < 40 and g < 90 and b < 145)
                shown = navy >= 2500
                found.append({'page': page_index + 1, 'navy_pixels': navy, 'visible': shown})
                visible += shown
    finally:
        document.close()
    return {'expected': expected, 'visible': visible, 'ribbons': found,
            'status': 'passed' if visible >= expected else 'failed'}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('pdf')
    ap.add_argument('render_dir')
    ap.add_argument('cards')
    ap.add_argument('--report', required=True)
    a = ap.parse_args()
    result = verify(a.pdf, a.render_dir, a.cards)
    write_json(a.report, result)
    print(result['status'], result['visible'], '/', result['expected'], 'visible ribbons')
    raise SystemExit(0 if result['status'] == 'passed' else 1)


if __name__ == '__main__':
    main()
