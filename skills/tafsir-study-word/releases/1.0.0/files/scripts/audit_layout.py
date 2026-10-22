"""Audit the actual DOCX design against the retained green/gold specification.

Structural checks complement, and never replace, reviewing rendered pages.
"""
import argparse
import hashlib
import json
import zipfile
from pathlib import Path
from xml.etree import ElementTree as E

W = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
WP = '{http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing}'
ASSETS = Path(__file__).resolve().parents[1] / 'assets'


def audit(path, spec):
    issues = []
    def require(ok, name):
        if not ok:
            issues.append(name)
    def attr(node, key):
        return node.get(W + key) if node is not None else None
    def near(node, key, cm):
        return node is not None and abs(int(node.get(W + key, -999)) - cm * 1440 / 2.54) <= 2
    with zipfile.ZipFile(path) as z:
        root = E.fromstring(z.read('word/document.xml'))
        styles = E.fromstring(z.read('word/styles.xml'))
        settings = E.fromstring(z.read('word/settings.xml'))
        sections = list(root.iter(W + 'sectPr'))
        require(len(sections) == 1, 'one_section')
        for sec in sections:
            size, margin = sec.find(W + 'pgSz'), sec.find(W + 'pgMar')
            require(near(size, 'w', spec['page_cm'][0]) and near(size, 'h', spec['page_cm'][1]), 'A4_page')
            require(all(near(margin, side, spec['margins_cm']) for side in ('top', 'right', 'bottom', 'left')), 'margins')
            require(all(near(margin, side, spec['header_footer_distance_cm']) for side in ('header', 'footer')), 'furniture_distance')
            require(sec.find(W + 'bidi') is not None, 'RTL_section')
            border = sec.find(W + 'pgBorders')
            require(attr(border, 'offsetFrom') == 'page', 'native_page_border')
            for side in ('top', 'left', 'bottom', 'right'):
                n = border.find(W + side) if border is not None else None
                require(attr(n, 'color') == spec['colors']['gold'] and attr(n, 'space') == str(spec['border_space_points']) and attr(n, 'sz') == str(spec['border_eighth_points']), 'gold_border_' + side)
        table = {s.get(W + 'styleId'): s for s in styles.findall(W + 'style')}
        def effective(style_id, prop, key):
            # Word often removes redundant direct properties during Save.
            # Audit the resulting inherited value, not XML spelling alone.
            seen = set()
            while style_id and style_id not in seen:
                seen.add(style_id)
                style = table.get(style_id)
                if style is None:
                    break
                node = style.find(f'{W}rPr/{W}{prop}')
                if node is not None:
                    value = node.get(W + key)
                    if value is not None:
                        return value
                    if prop == 'rtl':
                        return '1'
                parent = style.find(W + 'basedOn')
                style_id = attr(parent, 'val')
            node = styles.find(f'{W}docDefaults/{W}rPrDefault/{W}rPr/{W}{prop}')
            return attr(node, key)
        roles = [('Normal', spec['body_pt'], 'ink'), ('Title', spec['title_pt'], 'green'), ('Subtitle', spec['subtitle_pt'], 'gold'), ('Citation', spec['citation_pt'], 'muted'), ('Verse', spec['verse_pt'], 'green')]
        roles += [('Heading' + str(i), size, 'green') for i, size in enumerate(spec['heading_pt'], 1)]
        for name, pt, color in roles:
            s = table.get(name)
            rp = s.find(W + 'rPr') if s is not None else None
            require(rp is not None, name + '_style')
            if rp is None:
                continue
            require(all(effective(name, 'rFonts', key) == spec['font'] for key in ('ascii', 'hAnsi', 'eastAsia', 'cs')), name + '_font')
            require(effective(name, 'szCs', 'val') == str(pt * 2), name + '_Arabic_size')
            require(effective(name, 'color', 'val') == spec['colors'][color], name + '_color')
            require(effective(name, 'rtl', 'val') in ('1','true'), name + '_RTL_run')
        for p in root.find(W + 'body').findall(W + 'p'):
            if ''.join(t.text or '' for t in p.iter(W + 't')).strip():
                require(p.find(f'{W}pPr/{W}bidi') is not None, 'RTL_body_paragraph')
        require(not root.find(W + 'body').findall(W + 'tbl'), 'editable_body_paragraphs')
        require(not any(root.iter(W + 'pict')), 'no_page_screenshot_body')
        require(not any(settings.iter(W + 'documentProtection')), 'editable_no_protection')
        require(not any(root.iter(W + 'ins')) and not any(root.iter(W + 'del')), 'no_pending_tracked_changes')
        fields = ''.join(n.text or '' for n in root.iter(W + 'instrText'))
        require('TOC' in fields and '1-1' in fields, 'live_TOC')
        images = 0
        for name in ('word/header1.xml', 'word/footer1.xml'):
            part = E.fromstring(z.read(name))
            rows = list(part.iter(W + 'tr'))
            require(len(rows) == 1 and len(list(rows[0].iter(W + 'tc'))) == 3, name + '_three_cells')
            extents = list(part.iter(WP + 'extent')); images += len(extents)
            require(len(extents) == 2 and all(int(n.get('cx')) == 360000 and int(n.get('cy')) == 360000 for n in extents), name + '_corner_size')
            if 'footer' in name:
                require('PAGE' in ''.join(n.text or '' for n in part.iter(W + 'instrText')), 'live_page_number')
        require(images == 4, 'four_corner_ornaments')
        actual_images = {hashlib.sha256(z.read(n)).hexdigest() for n in z.namelist() if n.startswith('word/media/')}
        for corner in ASSETS.glob('corner-*.png'):
            require(hashlib.sha256(corner.read_bytes()).hexdigest() in actual_images, 'retained_corner_' + corner.name)
    return {'passed': not issues, 'issues': sorted(set(issues)), 'requires_visual_review': True}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--docx', required=True, type=Path)
    p.add_argument('--out', required=True, type=Path)
    p.add_argument('--style', type=Path, default=ASSETS / 'style-spec.json')
    a = p.parse_args()
    try:
        result = audit(a.docx, json.loads(a.style.read_text(encoding='utf-8')))
    except (OSError, KeyError, ValueError, E.ParseError, zipfile.BadZipFile) as exc:
        result = {'passed': False, 'issues': [str(exc)]}
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(result))
    return 0 if result['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
