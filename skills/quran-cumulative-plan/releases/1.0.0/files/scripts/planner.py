"""Deterministic data planning; XLSX authoring is handled by Artifact Tool."""
from __future__ import annotations

import json
import pathlib
import re
from collections import Counter

CATALOG_PATH = pathlib.Path(__file__).resolve().parent.parent / 'assets/catalog.json'


class PlanError(ValueError):
    """A missing input or a real conflict that requires the user's decision."""


def normalize(value):
    return re.sub(r'[\u064b-\u065f\u0670\s_\-]', '', str(value)).replace('أ', 'ا').replace('إ', 'ا').replace('آ', 'ا').replace('ى', 'ي').replace('ة', 'ه')


def integer(value, field, low=1, high=None):
    if isinstance(value, bool) or not re.fullmatch(r'\d+', str(value).strip()):
        raise PlanError(f'invalid_integer: {field}={value!r}')
    number = int(str(value).strip())
    if number < low or (high is not None and number > high):
        raise PlanError(f'out_of_range: {field}={number}')
    return number


def page_rank(page):
    return page - 305 if page >= 305 else page + 299


def filename_for(student):
    if not isinstance(student, str) or not student.strip():
        raise PlanError('missing_student_name: اسم الطالب مطلوب')
    cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1f]', ' ', student.strip())
    cleaned = re.sub(r'\s+', ' ', cleaned).strip(' .')
    if not cleaned or len(cleaned) > 150:
        raise PlanError('invalid_student_name: اسم ملف غير صالح')
    if re.fullmatch(r'CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9]', cleaned, re.I):
        cleaned = 'الطالب ' + cleaned
    return cleaned + '.xlsx'


def range_label(pages):
    runs = []
    for page in pages:
        if runs and page == runs[-1][1] + 1:
            runs[-1][1] = page
        else:
            runs.append([page, page])
    return 'تسميع ' + ' + '.join(f'({start} - {end})' for start, end in runs)


def build_plan(spec, catalog=None):
    catalog = catalog or json.loads(CATALOG_PATH.read_text(encoding='utf-8'))
    filename = filename_for(spec.get('student_name'))
    intervals = spec.get('cumulative_pages')
    if intervals is None:
        raise PlanError('missing_cumulative_pages: عدد صفحات الدفعة مطلوب')
    if isinstance(intervals, dict):
        intervals = {key: integer(value, f'cumulative_pages.{key}', high=604) for key, value in intervals.items()}
    else:
        intervals = {'default': integer(intervals, 'cumulative_pages', high=604)}
    selectors = spec.get('segments')
    if not isinstance(selectors, list) or not selectors:
        raise PlanError('missing_segments: حدد السور أو الأجزاء أو الصفحات')
    chapters = {s['number']: s for s in catalog['surahs']}
    juzs = {j['number']: j for j in catalog['juzs']}
    notices = []
    units = []

    def chapter_number(value):
        if re.fullmatch(r'\d+', str(value)):
            return integer(value, 'surah', high=114)
        name = re.sub(r'^سورة\s+', '', str(value).strip())
        matches = [s['number'] for s in catalog['surahs'] if normalize(s['name']) == normalize(name)]
        if len(matches) != 1:
            raise PlanError(f'unknown_surah: {value}')
        return matches[0]

    def add_named(kind, number):
        entry = (chapters if kind == 'surah' else juzs)[number]
        row = list(entry['test_row']) if entry['test_row'] else None
        if row is None:
            if kind == 'surah':
                row = [None, None, f'تسميع سورة {entry["name"]}', None, 1, None, 1, entry['name'], None, None, None]
                notices.append(f'السورة {entry["name"]}: الوزن 1؛ نقاط التسميع غير موجودة في المصدر فتُركت فارغة.')
            else:
                row = [None, None, f'تسميع الجزء {number} كاملًا', 400, 2, None, 1, None, entry['name'], None, None]
        override = spec.get('test_overrides', {}).get(f'{kind}:{number}', {})
        for key, column in [('points', 3), ('weight', 4)]:
            if key in override:
                value = override[key]
                if isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0:
                    raise PlanError(f'invalid_test_override: {kind}:{number}.{key}')
                row[column] = value
        units.append({'kind': kind, 'number': number, 'name': entry['name'], 'first_page': entry['first_page'], 'last_page': entry['last_page'], 'test_row': row})

    def add_pages(start, end):
        first = integer(start, 'from', high=604)
        last = integer(end, 'to', high=604)
        if first > last:
            raise PlanError('invalid_page_range: بداية النطاق أكبر من نهايته')
        exact = [(kind, entry['number']) for kind, collection in [('surah', catalog['surahs']), ('juz', catalog['juzs'])] for entry in collection if entry['first_page'] == first and entry['last_page'] == last]
        if len(exact) == 1:
            add_named(*exact[0])
        else:
            units.append({'kind': 'pages', 'number': None, 'name': f'الصفحات {first}–{last}', 'first_page': first, 'last_page': last, 'test_row': None})

    for segment in selectors:
        if not isinstance(segment, dict):
            raise PlanError('invalid_segment: يجب أن يكون النطاق كائنًا')
        kind = segment.get('type')
        if kind == 'surah':
            add_named('surah', chapter_number(segment.get('number', segment.get('name', ''))))
        elif kind == 'juz':
            add_named('juz', integer(segment.get('number'), 'juz', high=30))
        elif kind in ('surah_range', 'juz_range'):
            if kind == 'surah_range':
                first, last = chapter_number(segment.get('from', '')), chapter_number(segment.get('to', ''))
                base = 'surah'
            else:
                first, last = integer(segment.get('from'), 'juz.from', high=30), integer(segment.get('to'), 'juz.to', high=30)
                base = 'juz'
            if first > last:
                raise PlanError('invalid_range: حدد نطاقًا تصاعديًا أو قائمة وحدات مستقلة')
            for number in range(first, last + 1):
                add_named(base, number)
        elif kind in ('pages', 'page_range'):
            if 'numbers' in segment:
                if not isinstance(segment['numbers'], list) or not segment['numbers']:
                    raise PlanError('invalid_page_numbers')
                numbers = sorted(set(integer(n, 'page', high=604) for n in segment['numbers']))
                runs = []
                for number in numbers:
                    if runs and number == runs[-1][-1] + 1:
                        runs[-1].append(number)
                    else:
                        runs.append([number])
                for run in runs:
                    add_pages(run[0], run[-1])
            else:
                add_pages(segment.get('from'), segment.get('to', segment.get('from')))
        else:
            raise PlanError(f'unknown_segment_type: {kind}')

    distinct = {}
    for unit in units:
        key = (unit['kind'], unit['number']) if unit['number'] else ('pages', unit['first_page'], unit['last_page'])
        distinct.setdefault(key, unit)
    units = list(distinct.values())
    for unit in units:
        unit['pages'] = sorted(range(unit['first_page'], unit['last_page'] + 1), key=page_rank)
    units.sort(key=lambda u: (page_rank(u['pages'][0]), u['first_page'], u['kind'], u['number'] or 0))
    for i, first in enumerate(units):
        for second in units[i + 1:]:
            shared = set(first['pages']) & set(second['pages'])
            shared_surah_boundary = (first['kind'] == second['kind'] == 'surah' and len(shared) == 1 and first['last_page'] == second['first_page'])
            if shared and not shared_surah_boundary:
                if spec.get('overlap_policy') != 'independent':
                    raise PlanError(f'overlap: {first["name"]} / {second["name"]}; حدد هل تريد وحدتين مستقلتين أم نطاقًا واحدًا')
                notices.append(f'تداخل مقصود بوحدتين مستقلتين: {first["name"]} / {second["name"]}')
            elif shared:
                notices.append(f'صفحة مشتركة بين {first["name"]} و{second["name"]}: {next(iter(shared))}؛ أدرجت ضمن السورتين.')

    events = []
    group_count = 0
    for index, unit in enumerate(units):
        interval = intervals.get(unit['kind'], intervals.get('default'))
        if interval is None:
            raise PlanError(f'missing_cumulative_pages: {unit["kind"]}')
        pages = unit['pages']
        if len(pages) < interval and not spec.get('allow_short_units', False):
            raise PlanError(f'too_short: {unit["name"]}: {len(pages)} صفحات أقل من {interval}؛ يلزم تقليل الدفعة أو السماح بوحدة قصيرة')
        if len(pages) < interval:
            notices.append(f'وحدة قصيرة مسموحة صراحةً: {unit["name"]} ({len(pages)} صفحات).')
        batches = [pages[start:start + interval] for start in range(0, len(pages), interval)]
        if len(batches) > 1 and len(batches[-1]) < interval:
            batches[-2].extend(batches.pop())
        unit['batch_sizes'] = [len(batch) for batch in batches]
        group_count += len(batches)
        sequence = 0
        covered = []

        def emit(page, row):
            nonlocal sequence
            events.append((page_rank(page), index, sequence, row))
            sequence += 1

        for batch_index, batch in enumerate(batches):
            for page in batch:
                emit(page, [None, None, page, catalog['pages'][str(page)]['points'], 1, None, None, None, None, None, None])
            covered.extend(batch)
            final_with_test = batch_index == len(batches) - 1 and unit['test_row'] is not None
            if not final_with_test:
                emit(batch[-1], [None, None, range_label(covered), 20, 0, None, None, None, None, None, None])
        if unit['test_row']:
            emit(pages[-1], list(unit['test_row']))
        unit['_last_sequence'] = sequence

    full_juzs = {u['number']: (i, u) for i, u in enumerate(units) if u['kind'] == 'juz'}
    for start in range(1, 31, 3):
        numbers = [start, start + 1, start + 2]
        if all(number in full_juzs for number in numbers):
            last_index, last_unit = max((full_juzs[number] for number in numbers), key=lambda pair: (page_rank(pair[1]['pages'][-1]), pair[0]))
            original = catalog['triple_tests'].get('+'.join(map(str, numbers)))
            triple = list(original) if original else [None, None, f'تسميع الأجزاء ({start} + {start + 1} + {start + 2})', 600, 3, 1, 1, None, None, ' + '.join(map(str, numbers)), None]
            events.append((page_rank(last_unit['pages'][-1]), last_index, last_unit['_last_sequence'], triple))
    events.sort(key=lambda item: item[:3])
    rows = []
    for number, (_, _, _, row) in enumerate(events, 1):
        row[0], row[1] = None, number
        rows.append(row)
    assert all(len(row) == 11 and row[0] is None for row in rows)
    assert not any(row[4] == 0 and (rows[i + 1][7] or rows[i + 1][8]) for i, row in enumerate(rows[:-1]))
    ranks = [page_rank(row[2]) for row in rows if type(row[2]) is int]
    assert ranks == sorted(ranks)
    page_counts = Counter(row[2] for row in rows if type(row[2]) is int)
    return {
        'student_name': spec['student_name'].strip(), 'filename': filename, 'headers': catalog['headers'], 'rows': rows,
        'units': [{key: value for key, value in u.items() if key not in ('test_row', '_last_sequence')} for u in units],
        'notices': list(dict.fromkeys(notices)),
        'summary': {'records': len(rows), 'page_rows': sum(page_counts.values()), 'unique_pages': len(page_counts), 'cumulative_rows': sum(row[4] == 0 for row in rows), 'certificate_rows': sum(row[6] == 1 for row in rows), 'groups': group_count},
    }
