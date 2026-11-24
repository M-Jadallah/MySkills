"""Validate preserved source text, ayah coverage, vocalization and question keys."""
import argparse
import json
import re
import unicodedata
from collections import Counter
from pathlib import Path

WORD_RE = re.compile(r'[\u0621-\u064a\u064b-\u065f\u0670\u0671]+')

def bare(text):
    text = ''.join(c for c in str(text) if unicodedata.category(c) != 'Mn' and c not in 'ـۖۗۘۙۚۛۜ')
    return re.sub(r'\s+', ' ', text.replace('﴿', '').replace('﴾', '')).strip()

def visible_texts(course):
    for key in ['program_name', 'cover_title', 'course_title']:
        yield key, course.get(key, '')
    for ui, unit in enumerate(course.get('units', [])):
        for key in ['title', 'scope', 'basmala']:
            if unit.get(key): yield f'unit[{ui}].{key}', unit[key]
        for block in unit.get('blocks', []):
            yield block['id'] + '.title', block.get('title', '')
            for ayah in block.get('ayahs', []):
                yield block['id'] + '.ayah', ayah.get('text', '')
            for pi, para in enumerate(block.get('paragraphs', [])):
                for segment in para.get('segments', []):
                    yield f'{block["id"]}.paragraph[{pi}]', segment.get('text', '')
    for question in course.get('questions', []):
        for key in ['prompt', 'explanation', 'reference']:
            yield f'question[{question.get("id")}].{key}', question.get(key, '')
        for opt in question.get('options', []): yield 'option', opt
    for source in course.get('sources', []):
        for key in ['label', 'bibliography']:
            if source.get(key): yield 'source.' + key, source[key]

def validate(course):
    errors, warnings = [], []
    for key in ['program_name', 'cover_title', 'course_title', 'units', 'questions', 'sources']:
        if not course.get(key): errors.append(f'Missing nonempty {key}')
    source_ids = [s.get('id') for s in course.get('sources', [])]
    if len(source_ids) != len(set(source_ids)) or None in source_ids:
        errors.append('Sources need unique nonempty ids')
    corrections = course.get('corrections', [])
    for correction in corrections:
        if not all(correction.get(k) for k in ['before', 'after', 'reason', 'source_url']):
            errors.append('A correction lacks before/after/reason/source_url')
    blocks = {}
    for unit in course.get('units', []):
        if not isinstance(unit.get('chapter'), int) or not 1 <= unit['chapter'] <= 114:
            errors.append('Invalid chapter number')
        actual = []
        for block in unit.get('blocks', []):
            bid = block.get('id')
            if not bid or bid in blocks: errors.append(f'Duplicate/missing block id {bid}')
            blocks[bid] = block
            start, end = block.get('start_ayah'), block.get('end_ayah')
            if not isinstance(start, int) or not isinstance(end, int) or not 1 <= start <= end:
                errors.append(f'{bid}: invalid ayah range'); continue
            nums = [a.get('number') for a in block.get('ayahs', [])]
            if nums != list(range(start, end + 1)):
                errors.append(f'{bid}: missing, duplicate or out-of-order ayahs')
            actual.extend(nums)
            if not block.get('paragraphs'): errors.append(f'{bid}: empty tafsir')
            for pi, para in enumerate(block.get('paragraphs', [])):
                if not para.get('source'): errors.append(f'{bid}/{pi}: missing preserved source')
                if para.get('source_id') not in source_ids: errors.append(f'{bid}/{pi}: unknown source_id')
                segments = para.get('segments', [])
                if not segments: errors.append(f'{bid}/{pi}: no segments')
                for segment in segments:
                    if segment.get('kind') not in ['tafsir', 'quran']:
                        errors.append(f'{bid}/{pi}: invalid segment kind')
                    if not segment.get('text', '').strip(): errors.append(f'{bid}/{pi}: blank segment')
                    if segment.get('kind') == 'quran' and any(c in segment.get('text', '') for c in '﴿﴾'):
                        errors.append(f'{bid}/{pi}: quran segment must not include quotation brackets')
                source = bare(para.get('source', ''))
                for correction in corrections:
                    source = source.replace(bare(correction.get('before', '')), bare(correction.get('after', '')))
                authored = bare(''.join(s.get('text', '') for s in segments))
                if source != authored: errors.append(f'{bid}/{pi}: source words changed or dropped')
        start, end = unit.get('start_ayah'), unit.get('end_ayah')
        if not isinstance(start, int) or not isinstance(end, int) or start < 1 or end < start:
            errors.append('Unit needs a valid start_ayah/end_ayah')
        elif actual != list(range(start, end + 1)):
            errors.append(f'{unit.get("title")}: blocks do not cover requested ayahs exactly')
    expected = course.get('questions_expected', {'mcq': 10, 'tf': 10})
    questions = course.get('questions', [])
    counts = Counter(q.get('type') for q in questions)
    if dict(counts) != expected: errors.append(f'Question count {dict(counts)} != {expected}')
    if [q.get('id') for q in questions] != list(range(1, len(questions) + 1)):
        errors.append('Question ids must be consecutive from 1')
    if [q.get('type') for q in questions] != ['mcq'] * expected.get('mcq', 0) + ['tf'] * expected.get('tf', 0):
        errors.append('Order questions as all mcq followed by all tf')
    for q in questions:
        label = f'question[{q.get("id")}]'
        if q.get('type') == 'mcq':
            options = q.get('options', [])
            if len(options) != 4 or len({bare(o) for o in options}) != 4:
                errors.append(f'{label}: need four distinct options')
            if type(q.get('answer')) is not int or not 0 <= q['answer'] < 4:
                errors.append(f'{label}: invalid answer index')
        elif q.get('type') == 'tf':
            if type(q.get('answer')) is not bool: errors.append(f'{label}: answer must be boolean')
        else: errors.append(f'{label}: invalid question type')
        block = blocks.get(q.get('block_id'))
        evidence = bare(q.get('evidence', ''))
        if not block: errors.append(f'{label}: unknown block_id')
        else:
            text = bare(' '.join(p.get('source', '') for p in block.get('paragraphs', [])))
            if not evidence or evidence not in text: errors.append(f'{label}: evidence absent from source block')
        if not q.get('explanation') or not q.get('reference'):
            errors.append(f'{label}: missing explanation or ayah reference')
    uncovered = []
    for unit in course.get('units', []):
        ids = {b['id'] for b in unit.get('blocks', [])}
        if not any(q.get('block_id') in ids for q in questions): uncovered.append(unit.get('title'))
    if uncovered: errors.append('Units have no questions: ' + ', '.join(uncovered))
    unvocalized = []
    for location, text in visible_texts(course):
        if not isinstance(text, str): errors.append(f'{location}: text is not a string'); continue
        for word in WORD_RE.findall(text):
            if len(word) > 1 and word != 'هـ' and not any(unicodedata.category(c) == 'Mn' for c in word):
                unvocalized.append((location, word))
    if unvocalized: errors.append('Words have no vowel marks: ' + repr(unvocalized[:25]))
    warnings.append('Vowel-mark coverage does not establish grammatical or Quranic correctness; review the text manually.')
    return {'ok': not errors, 'errors': errors, 'warnings': warnings,
            'paragraphs': sum(len(b.get('paragraphs', [])) for b in blocks.values()),
            'question_counts': dict(counts)}

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('data', type=Path)
    parser.add_argument('--report', type=Path)
    args = parser.parse_args()
    result = validate(json.loads(args.data.read_text(encoding='utf-8-sig')))
    text = json.dumps(result, ensure_ascii=False, indent=2)
    if args.report: args.report.write_text(text, encoding='utf-8')
    print(text)
    raise SystemExit(0 if result['ok'] else 1)

if __name__ == '__main__': main()
