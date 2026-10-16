"""Structural/source checks. Semantic fidelity and correct Arabic vowels need agent review."""
from __future__ import annotations
import argparse
import json
import re
import unicodedata
from pathlib import Path
from zipfile import ZipFile
from lxml import etree
from build_lesson import check_content, plan_diagram, ROOT, TOKENS, FONT
from smartart_backend import validate_smartart

NS = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main', 'v': 'urn:schemas-microsoft-com:vml'}
W = '{' + NS['w'] + '}'
MARKS = re.compile('[\u064b-\u065f\u0670\u06d6-\u06ed]')
WORDS = re.compile('[\u0621-\u063a\u0641-\u065f\u0670\u0671]+')


def load_source(path):
    raw = path.read_bytes()
    encodings = ['utf-8-sig']
    if raw.startswith((b'\xff\xfe', b'\xfe\xff')):
        encodings.insert(0, 'utf-16')
    encodings.append('cp1256')
    for encoding in encodings:
        try:
            text = raw.decode(encoding)
            if '\x00' not in text and '\ufffd' not in text:
                return text.replace('\r\n', '\n').replace('\r', '\n')
        except UnicodeError:
            pass
    raise ValueError('Source decoding failed. Preserve raw bytes and determine encoding; do not discard undecodable characters.')


def content_texts(data):
    def text(value):
        if isinstance(value, str):
            yield value
        else:
            yield ''.join(s['text'] for s in value)
    def node(n):
        yield n['label']
        if n.get('relation'):
            yield n['relation']
        for c in n.get('children', []):
            yield from node(c)
    yield data['title']
    if data.get('scope'):
        yield from text(data['scope'])
    for topic in data['topics']:
        yield topic['title']
        for block in topic['blocks']:
            if block.get('title'):
                yield block['title']
            if block['type'] == 'diagram':
                if 'root' in block:
                    yield from node(block['root'])
                else:
                    for n in block['nodes']:
                        yield from node(n)
            elif block['type'] == 'table':
                for c in block['columns']:
                    yield from text(c)
                for row in block['rows']:
                    for cell in row:
                        yield from text(cell)
            else:
                yield from text(block['text'])
    for item in data['summary']:
        yield from text(item['text'])


def norm(s):
    return ' '.join(unicodedata.normalize('NFC', s).split())


def check(data, path, source):
    errors, warnings = [], []
    ids = check_content(data)
    summary_ids = {x['id'] for x in data['summary']}
    visual_ids = {b['id'] for t in data['topics'] for b in t['blocks'] if b['type'] in ('diagram', 'table')}
    units = data.get('coverage', {}).get('units', [])
    if not units:
        errors.append('Missing internal coverage units')
    unit_ids = set()
    for unit in units:
        uid = unit['id']
        if not unit.get('claim'):
            errors.append('Unit has no explicit scientific claim: ' + uid)
        if uid in unit_ids:
            errors.append('Duplicate unit ID: ' + uid)
        unit_ids.add(uid)
        if not unit.get('source_quotes'):
            errors.append('Unit has no exact source evidence: ' + uid)
        for quote in unit.get('source_quotes', []):
            if not quote or quote not in source:
                errors.append('Unit quote not found verbatim in source: ' + uid)
        for key, targets in [('visual_refs', visual_ids), ('summary_refs', summary_ids)]:
            refs = unit.get(key, [])
            if not refs or any(ref not in targets for ref in refs):
                errors.append('Missing or invalid ' + key + ': ' + uid)
    accounting = data.get('coverage', {}).get('source_accounting', [])
    accounted = bytearray(len(source))
    if not accounting:
        errors.append('Missing source accounting: every non-whitespace source character needs an explained span')
    for span in accounting:
        lo, hi = span['start'], span['end']
        if not 0 <= lo < hi <= len(source):
            errors.append('Invalid source accounting offsets')
            continue
        if any(accounted[lo:hi]):
            errors.append('Overlapping source accounting spans')
        accounted[lo:hi] = b'\x01' * (hi-lo)
        classification = span.get('kind')
        if classification not in ('scientific', 'filler', 'repetition', 'metadata'):
            errors.append('Invalid source accounting kind')
        if classification in ('scientific', 'repetition') and (not span.get('units') or any(x not in unit_ids for x in span['units'])):
            errors.append('Scientific/repeated source span has no valid units')
        if classification in ('filler', 'metadata') and not span.get('reason'):
            errors.append('Excluded source span needs an internal reason')
    missing = [i for i, char in enumerate(source) if not char.isspace() and not accounted[i]]
    if missing:
        errors.append(f'{len(missing)} non-whitespace source characters are unaccounted for')

    with ZipFile(path) as package:
        parts = {name: etree.fromstring(package.read(name)) for name in package.namelist() if name.startswith('word/') and name.endswith('.xml') and not name.startswith('word/theme/')}
        main = parts['word/document.xml']
        plans=[panel for topic in data['topics'] for block in topic['blocks'] if block['type']=='diagram' for panel in plan_diagram(block)]
        smartart=validate_smartart(package,main,plans,FONT)
        errors.extend(smartart['errors'])
        xml_text = norm(' '.join(main.xpath('//w:t/text()', namespaces=NS)+smartart['texts']))
        for expected in content_texts(data):
            if norm(expected) not in xml_text:
                errors.append('Content absent from native Word text: ' + expected[:65])
        for name in ['word/document.xml', 'word/header1.xml', 'word/footer1.xml']:
            if name not in parts:
                errors.append('Missing document part: ' + name)
                continue
            for run in parts[name].xpath('//w:r[w:t[string-length(.) > 0]]', namespaces=NS):
                fonts = run.find(W+'rPr/'+W+'rFonts')
                if fonts is None or any(fonts.get(W+key) != FONT for key in ('ascii', 'hAnsi', 'eastAsia', 'cs')):
                    errors.append('Text run is not explicitly Traditional Arabic: ' + name)
                    break
        for style in parts['word/styles.xml'].xpath('//w:style/w:rPr/w:rFonts', namespaces=NS):
            if any(style.get(W+key) != FONT for key in ('ascii', 'hAnsi', 'eastAsia', 'cs')):
                errors.append('A style font differs from the locked font')
                break
        if not parts['word/fontTable.xml'].xpath('//w:font[@w:name="Traditional Arabic"]', namespaces=NS):
            errors.append('Traditional Arabic is missing from fontTable')
        with ZipFile(ROOT/'assets/lesson-template.docx') as template:
            for member in ('word/header1.xml', 'word/footer1.xml', 'word/styles.xml', 'word/fontTable.xml'):
                if package.read(member) != template.read(member):
                    errors.append('Locked template part changed: ' + member)
        for sect in main.xpath('//w:sectPr', namespaces=NS):
            size = sect.find(W+'pgSz')
            if size is None or abs(int(size.get(W+'w', 0))-11906) > 2 or abs(int(size.get(W+'h', 0))-16838) > 2:
                errors.append('Page geometry is not A4 portrait')
        for forbidden in ('//w:ins', '//w:del', '//w:commentRangeStart'):
            if main.xpath(forbidden, namespaces=NS):
                errors.append('Editorial markup remains: ' + forbidden)
        if any('comments' in name.lower() for name in package.namelist()):
            errors.append('Comment part remains in final document')
        plain = MARKS.sub('', xml_text)
        if 'مواضع تحتاج مراجعة' in plain:
            errors.append('Forbidden review section remains')
        summary = TOKENS['fixed_labels']['summary']
        body_children = list(main.find(W+'body'))
        summary_index = None
        for i, child in enumerate(body_children):
            if norm(''.join(child.xpath('.//w:t/text()', namespaces=NS))) == norm(summary):
                summary_index = i
        if summary_index is None:
            errors.append('Final summary heading missing')
        elif any(ch.tag in (W+'tbl',) or ch.xpath('.//w:drawing | .//w:pict', namespaces=NS) for ch in body_children[summary_index+1:]):
            errors.append('A table or diagram follows the final summary')
        diagrams = smartart['count']
    unmarked = sorted({w for txt in content_texts(data) for w in WORDS.findall(txt) if not MARKS.search(w)})
    if unmarked:
        warnings.append({'unvocalized_tokens_for_manual_review': unmarked})
    warnings.append('Machine checks cannot prove source interpretation, completeness of extracted units, or correct Arabic inflection. Review every unit and every rendered page.')
    return {'passed_structural_checks': not errors, 'errors': sorted(set(errors)), 'warnings': warnings, 'units': len(units), 'native_smartart_panels': diagrams}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--content', required=True, type=Path)
    p.add_argument('--docx', required=True, type=Path)
    p.add_argument('--source', required=True, type=Path)
    p.add_argument('--report', required=True, type=Path)
    a = p.parse_args()
    result = check(json.loads(a.content.read_text(encoding='utf-8-sig')), a.docx, load_source(a.source))
    a.report.parent.mkdir(parents=True, exist_ok=True)
    a.report.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(result, ensure_ascii=True, indent=2))
    raise SystemExit(0 if result['passed_structural_checks'] else 1)


if __name__ == '__main__':
    main()
