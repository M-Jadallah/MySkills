"""Check that scientific and page reviews actually cover the version delivered.

This verifies review evidence and freshness, not the truth of a reviewer's
judgments. Never auto-fill passing attestations from a mechanical audit.
"""
import argparse
import hashlib
import json
from pathlib import Path

CHECKS = ('coverage', 'literal_quotes', 'preferences', 'terms', 'stories',
          'themes_and_proofs', 'benefits', 'names_and_attributes', 'vocalization')
DOCUMENT_CHECKS = ('front_matter_vocalization', 'design_fidelity', 'field_accuracy', 'editable_text')


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def check(study, sources, coverage, review, files):
    errors = []
    def fail(code, path, message):
        errors.append({'code': code, 'path': path, 'message': message})
    def text(value):
        return isinstance(value, str) and bool(value.strip())

    if review.get('schema_version') != 1:
        fail('review_schema', 'review', 'Expected schema_version 1')
    for name, path in files.items():
        if review.get('input_sha256', {}).get(name) != digest(path):
            fail('stale_review', name, 'Review must refer to the exact current file bytes')
    if review.get('open_issues') != []:
        fail('open_issues', 'review', 'Resolve material issues before declaring a complete release')
    if not text(review.get('reviewer')) or not text(review.get('reviewed_at')):
        fail('review_identity', 'review', 'Record reviewer and actual review date')
    for key in DOCUMENT_CHECKS:
        item = review.get('document_checks', {}).get(key, {})
        if item.get('status') != 'pass' or not text(item.get('note')):
            fail('document_review_missing', key, 'Review cover, TOC, methodology, references, header/footer and design, not only verse bodies')
    readings = {(r.get('source_id'), r.get('block_id')): r for r in review.get('source_reading', [])}
    for source in sources['sources']:
        for block in source['blocks']:
            pair = (source['id'], block['id'])
            r = readings.get(pair, {})
            if r.get('status') != 'read_and_inventoried' or not text(r.get('note')):
                fail('unread_source_block', '.'.join(pair), 'Every original block, including preambles, must be read and inventoried')
            if r.get('start') != block['start'] or r.get('end') != block['end']:
                fail('reading_extent', '.'.join(pair), 'Reading record must cover the complete block')
    reviews = {r.get('key'): r for r in review.get('verses', [])}
    for vi, verse in enumerate(study['verses']):
        r = reviews.get(verse['key'], {})
        checks = r.get('checks', {})
        for key in CHECKS:
            item = checks.get(key, {})
            if item.get('status') != 'pass' or not text(item.get('note')):
                fail('scientific_review_missing', verse['key'] + '.' + key, 'Record the actual finding, not a blanket statement of completion')
        if any(str(axis) in verse.get('empty_axes', {}) for axis in (2, 5, 6)):
            fail('material_axis_gap', verse['key'], 'An absent opinions/themes/benefits axis is a material gap, not a complete study')
        names = verse.get('names', {})
        if names.get('kind') not in ('none', 'name', 'attribute', 'action', 'disputed'):
            fail('names_kind', verse['key'], 'Record whether a name, attribute, action, disputed referent, or none occurs')
        if names.get('kind') != 'none' and not names.get('references'):
            fail('alnahj_missing', verse['key'], 'A relevant divine name/attribute discussion requires verified Al-Nahj references')
        for gi, group in enumerate(verse['groups']):
            for qi, q in enumerate(group['quotes']):
                check_quote(q, f'{verse["key"]}.groups[{gi}].quotes[{qi}]', fail)
        check_quote(verse['summary'], verse['key'] + '.summary', fail, summary=True)
        for si, story in enumerate(verse['stories']):
            check_quote(story['quote'], f'{verse["key"]}.stories[{si}]', fail)
    for ci, item in enumerate(coverage['items']):
        if not text(item.get('meaning')) or not item.get('source_spans'):
            fail('coverage_not_inventory', f'coverage.items[{ci}]', 'Each decision needs a distinct meaning and exact source span, not one generic row per book')
        source = next((s for s in sources['sources'] if s['id'] == item.get('source_id')), {})
        block = next((b for b in source.get('blocks', []) if b['id'] == item.get('block_id')), {})
        for span in item.get('source_spans', []):
            start, end = span.get('start'), span.get('end')
            if type(start) is not int or type(end) is not int or not (block.get('start', 0) <= start < end <= block.get('end', 0)):
                fail('coverage_span', f'coverage.items[{ci}]', 'Coverage span must lie in its named original block')
    verification = {r.get('path'): r for r in review.get('verification', [])}
    for vi, verse in enumerate(study['verses']):
        paths = []
        for ti, theme in enumerate(verse['themes']):
            for genre in ('hadith', 'poetry'):
                paths.extend(f'study.verses[{vi}].themes[{ti}].{genre}[{pi}]' for pi in range(len(theme[genre])))
        paths.extend(f'study.verses[{vi}].names.references[{ni}]' for ni in range(len(verse['names']['references'])))
        for path in paths:
            entry = verification.get(path, {})
            if entry.get('status') != 'verified' or any(not text(entry.get(k)) for k in ('url', 'locator', 'checked_at', 'finding')):
                fail('unverified_evidence', path, 'Record opened primary source, exact location, date and substantive finding')
    visual = review.get('visual', {})
    if visual.get('fields_updated') is not True or not text(visual.get('engine')):
        fail('fields_not_updated', 'visual', 'Use an actual layout engine to refresh TOC/PAGE fields')
    try:
        import pypdfium2 as pdfium
        pdf = pdfium.PdfDocument(str(files['pdf']))
        count = len(pdf)
        pdf.close()
        pages = visual.get('pages', [])
        if sorted(p.get('number', -1) for p in pages) != list(range(1, count + 1)):
            fail('unreviewed_pages', 'visual.pages', 'List every actual final PDF page exactly once')
        for page in pages:
            path = Path(page.get('path', ''))
            if not path.is_file() or page.get('sha256') != digest(path):
                fail('stale_page_image', str(path), 'Page image missing or changed after review')
            if page.get('status') != 'pass' or not text(page.get('note')):
                fail('page_review_missing', str(path), 'Record the result of viewing this page at readable original size')
    except Exception as exc:
        fail('pdf_review', 'visual', str(exc))
    return {'passed': not errors, 'errors': errors,
            'limitations': ['Attestations must be truthful; this gate cannot infer scholarly correctness or see pages on behalf of the reviewer.']}


def check_quote(q, path, fail, summary=False):
    spans = q.get('source_spans')
    if not isinstance(spans, list) or not spans:
        fail('quote_traceability', path, 'Exact original source spans are mandatory for release')
        return
    for left, right in zip(spans, spans[1:]):
        gap = (left.get('end'), right.get('start'))
        omissions = q.get('omissions', [])
        matches = [o for o in omissions if (o.get('start'), o.get('end')) == gap]
        kinds = ('isnad', 'footnote', 'summary_selection') if summary and q.get('mode') == 'extracted' else ('isnad', 'footnote')
        if len(matches) != 1 or matches[0].get('kind') not in kinds or not matches[0].get('reason'):
            fail('unapproved_omission', path, 'Each gap must be an identified isnad or footnote with its exact bounds and reason')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('study', 'sources', 'coverage', 'quran', 'docx', 'pdf', 'review', 'out'):
        p.add_argument('--' + name, type=Path, required=True)
    a = p.parse_args()
    try:
        load = lambda path: json.loads(path.read_text(encoding='utf-8-sig'))
        from audit_study import Auditor
        study, sources, coverage = load(a.study), load(a.sources), load(a.coverage)
        base = Auditor(study, sources, load(a.quran), coverage).run(a.docx)
        files = {name: getattr(a, name) for name in ('study', 'sources', 'coverage', 'quran', 'docx', 'pdf')}
        result = check(study, sources, coverage, load(a.review), files)
        from audit_layout import audit, ASSETS
        layout = audit(a.docx, load(ASSETS / 'style-spec.json'))
        result['errors'] += [{'code': 'layout', 'path': 'docx', 'message': name} for name in layout['issues']]
        result['errors'] = base['errors'] + result['errors']
        result['passed'] = not result['errors']
        result['mechanical_warnings'] = base['warnings']
    except Exception as exc:
        result = {'passed': False, 'errors': [{'code': 'invalid_release_input', 'message': str(exc)}]}
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'passed': result['passed'], 'errors': len(result['errors']), 'report': str(a.out.resolve())}))
    return 0 if result['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
