#!/usr/bin/env python3
"""Check text preservation and the agreed Word formatting; not a hadith authenticator."""
import argparse
import json
import sys
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

W = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
NS = {'w': W[1:-1]}

def require(ok, message):
    if not ok:
        raise ValueError(message)

def text_of(element):
    return ''.join(element.itertext()) if element.tag == W + 't' else ''.join(t.text or '' for t in element.iter(W + 't'))

def props(element):
    values = {}
    if element is not None:
        for child in element:
            tag = child.tag.removeprefix(W)
            if tag == 'rFonts':
                for key in ('ascii', 'hAnsi', 'cs', 'eastAsia'):
                    if child.get(W + key):
                        values['font_' + key] = child.get(W + key)
            elif tag in ('sz', 'szCs', 'color'):
                values[tag] = child.get(W + 'val')
            elif tag in ('b', 'bCs'):
                values[tag] = child.get(W + 'val', 'true') not in ('0', 'false', 'off')
    return values

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('docx')
    parser.add_argument('--data')
    parser.add_argument('--without-relations', action='store_true', help='Verify the second edition omits relation text and its references')
    args = parser.parse_args()
    theme = json.loads((Path(__file__).resolve().parent.parent / 'assets' / 'design.json').read_text(encoding='utf-8'))
    with zipfile.ZipFile(args.docx) as zf:
        styles = ET.fromstring(zf.read('word/styles.xml'))
        document = ET.fromstring(zf.read('word/document.xml'))
        defaults = props(styles.find('w:docDefaults/w:rPrDefault/w:rPr', NS))
        style_nodes = styles.findall('w:style', NS)
        by_id = {s.get(W + 'styleId'): s for s in style_nodes}
        require(len(by_id) == len(style_nodes), 'Duplicate Word style IDs')
        def inherited(style_id):
            result = dict(defaults)
            style = by_id.get(style_id)
            if style is not None:
                parent = style.find('w:basedOn', NS)
                if parent is not None and parent.get(W + 'val') != style_id:
                    result.update(inherited(parent.get(W + 'val')))
                result.update(props(style.find('w:rPr', NS)))
            return result
        def style_id(p):
            s = p.find('w:pPr/w:pStyle', NS)
            return s.get(W + 'val') if s is not None else 'Normal'
        paragraphs = list(document.findall('.//w:body/w:p', NS))
        runs_checked = 0
        for p in paragraphs:
            sid = style_id(p)
            p_style = by_id.get(sid)
            bidi = p.find('w:pPr/w:bidi', NS)
            if bidi is None and p_style is not None:
                bidi = p_style.find('w:pPr/w:bidi', NS)
            require(bidi is not None and bidi.get(W + 'val', 'true') not in ('0', 'false'), f'Missing RTL paragraph: {sid}')
            alignment = p.find('w:pPr/w:jc', NS)
            if alignment is None and p_style is not None:
                alignment = p_style.find('w:pPr/w:jc', NS)
            expected_alignment = 'center' if sid == 'Title' else 'start'
            require(alignment is not None and alignment.get(W + 'val') == expected_alignment, f'Wrong logical RTL alignment in {sid}')
            for r in p.iter(W + 'r'):
                if not text_of(r):
                    continue
                effective = inherited(sid)
                effective.update(props(r.find('w:rPr', NS)))
                for key in ('ascii', 'hAnsi', 'cs', 'eastAsia'):
                    require(effective.get('font_' + key) == theme['font'], f'Wrong {key} font in {sid}')
                expected_size = str(2 * (theme['citation_pt'] if sid == 'Citation' else theme['relation_pt'] if sid == 'Relation' else theme['body_pt']))
                require(effective.get('sz') == expected_size and effective.get('szCs') == expected_size, f'Wrong Latin/Arabic size in {sid}')
                allowed = [theme['colors']['evidence'], theme['colors']['witness']] if sid == 'Evidence' else [theme['colors']['citation'] if sid == 'Citation' else theme['colors']['text']]
                require(effective.get('color', '').upper() in allowed, f'Wrong color in {sid}')
                if sid == 'Evidence' and effective.get('color') == theme['colors']['witness']:
                    require(effective.get('b') is True and effective.get('bCs') is True, 'Witness must be bold for Latin and Arabic scripts')
                runs_checked += 1
            if sid == 'Citation':
                require(not list(p.iter(W + 'br')) and not list(p.iter(W + 'cr')) and '\n' not in text_of(p) and '\r' not in text_of(p), 'Citation must be one continuous line without manual breaks')
            if sid == 'Evidence':
                evidence_style = by_id['Evidence']
                shading = p.find('w:pPr/w:shd', NS)
                if shading is None:
                    shading = evidence_style.find('w:pPr/w:shd', NS)
                require(shading is not None and shading.get(W + 'fill') == theme['colors']['evidence_fill'], 'Missing pale evidence box fill')
                for edge in ('top', 'bottom', 'left', 'right'):
                    border = p.find(f'w:pPr/w:pBdr/w:{edge}', NS)
                    if border is None:
                        border = evidence_style.find(f'w:pPr/w:pBdr/w:{edge}', NS)
                    require(border is not None and border.get(W + 'color') == theme['colors']['evidence_border'] and border.get(W + 'val') == 'single', f'Missing evidence box {edge} border')
        if args.without_relations:
            require(not any(style_id(p) == 'Relation' for p in paragraphs), 'The edition without relations still contains a relation paragraph')
            require(not any('مرجع وجه الارتباط:' in text_of(p) for p in paragraphs), 'Relation-only source still appears in the edition without relations')
        for name in ('Title', 'Heading1'):
            require(name in by_id, f'Missing {name} style')
        title_shading = by_id['Title'].find('w:pPr/w:shd', NS)
        require(title_shading is not None and title_shading.get(W + 'fill') == theme['colors']['title_fill'], 'Wrong title band fill')
        for sid, edge in [('Title', 'top'), ('Heading1', 'bottom')]:
            line = by_id[sid].find(f'w:pPr/w:pBdr/w:{edge}', NS)
            require(line is not None and line.get(W + 'color') == theme['colors']['evidence'], f'Missing burgundy {edge} line in {sid}')
        require(not document.findall('.//w:tbl', NS), 'Unexpected layout table')
        size = document.find('.//w:sectPr/w:pgSz', NS)
        require(size is not None and int(size.get(W + 'w')) == theme['page']['width'] and int(size.get(W + 'h')) == theme['page']['height'], 'Wrong page size')
        footers = [ET.fromstring(zf.read(n)) for n in zf.namelist() if n.startswith('word/footer') and n.endswith('.xml')]
        require(any('PAGE' in (f.get(W + 'instr', '')) for root in footers for f in root.iter(W + 'fldSimple')), 'Missing PAGE field')
        quotes_checked = 0
        if args.data:
            data = json.loads(Path(args.data).read_text(encoding='utf-8-sig'))
            require(any(style_id(p) == 'Title' and text_of(p) == data['topic'] for p in paragraphs), 'Topic title missing or changed')
            used = set()
            for section in data['sections']:
                require(any(style_id(p) == 'Heading1' and text_of(p) == section['title'] for p in paragraphs), 'Section title missing or changed')
                for item in section['evidence']:
                    target = ('﴿' if item['type'] == 'quran' else '(') + item['text'] + ('﴾' if item['type'] == 'quran' else ')')
                    hits = [(i, p) for i, p in enumerate(paragraphs) if i not in used and style_id(p) == 'Evidence' and text_of(p) == target]
                    require(hits, f"Text was omitted or changed: {item['id']}")
                    index, p = hits[0]
                    used.add(index)
                    expected_intro = 'قال تعالى:' if item['type'] == 'quran' else item['intro']
                    require(index > 0 and style_id(paragraphs[index - 1]) == 'Intro' and text_of(paragraphs[index - 1]) == expected_intro, f"Introduction missing or changed: {item['id']}")
                    following = []
                    for later in paragraphs[index + 1:]:
                        if style_id(later) in ('Intro', 'Heading1', 'Evidence'):
                            break
                        following.append(later)
                    note_paragraphs = [later for later in following if style_id(later) == 'Citation']
                    require(len(note_paragraphs) == 1, f"All documentation must be in one paragraph: {item['id']}")
                    notes = text_of(note_paragraphs[0])
                    relations = [text_of(later) for later in following if style_id(later) == 'Relation']
                    if args.without_relations:
                        require(not relations, f"Relation text must be omitted: {item['id']}")
                    else:
                        require(any(item['relation']['text'] in s for s in relations), f"Relation text missing or changed: {item['id']}")
                    if not args.without_relations and item['relation'].get('source'):
                        require(item['relation']['source']['reference'] in notes, f"Relation source missing: {item['id']}")
                    if item['type'] == 'quran':
                        number = str(item['ayah_number']).translate(str.maketrans('0123456789', '٠١٢٣٤٥٦٧٨٩'))
                        require(f"سورة {item['surah_name']}، الآية {number}" in notes, f"Quran reference missing or changed: {item['id']}")
                    else:
                        grade = {'sahih': 'صحيح', 'hasan': 'حسن', 'disputed': 'مختلف في صحته'}[item['status']]
                        require(item['source']['reference'] in notes and f'الحكم: {grade}.' in notes, f"Hadith source or grade missing: {item['id']}")
                        for j in item['judgments']:
                            required = [j['scholar'], j['ruling']]
                            if j['source']['url'] != item['source']['url']:
                                required.append(j['source']['reference'])
                            require(all(value.replace('\n', ' ').replace('\r', ' ').replace('\t', ' ') in notes for value in required), f"A documented judgment is missing: {item['id']}")
                        if item.get('dispute_explanation'):
                            require(item['dispute_explanation'] in notes, f"Scope explanation missing: {item['id']}")
                    actual = []
                    actual_bold = []
                    for r in p.iter(W + 'r'):
                        rp = inherited('Evidence')
                        rp.update(props(r.find('w:rPr', NS)))
                        actual.extend([rp['color']] * len(text_of(r)))
                        actual_bold.extend([rp.get('b', False) and rp.get('bCs', False)] * len(text_of(r)))
                    expected = [theme['colors']['evidence']] * len(target)
                    expected_bold = [False] * len(target)
                    for witness in item['witnesses']:
                        quote = witness if isinstance(witness, str) else witness['quote']
                        occurrence = 1 if isinstance(witness, str) else witness.get('occurrence', 1)
                        start = -len(quote)
                        for _ in range(occurrence):
                            start = item['text'].find(quote, start + len(quote))
                        require(start >= 0, 'Witness missing from data')
                        for k in range(start + 1, start + 1 + len(quote)):
                            expected[k] = theme['colors']['witness']
                            expected_bold[k] = True
                    require(actual == expected, f"Witness color changed the wrong characters: {item['id']}")
                    require(actual_bold == expected_bold, f"Witness bold formatting changed the wrong characters: {item['id']}")
                    quotes_checked += 1
            require(quotes_checked == sum(1 for p in paragraphs if style_id(p) == 'Evidence'), 'Unexpected extra evidence paragraph')
    print(json.dumps({'valid': True, 'runs_checked': runs_checked, 'complete_quotes_checked': quotes_checked}, ensure_ascii=False))

if __name__ == '__main__':
    try:
        main()
    except (ValueError, KeyError, ET.ParseError, zipfile.BadZipFile) as error:
        print(str(error), file=sys.stderr)
        sys.exit(1)
