"""Build one integrated course DOCX from reviewed workers and canonical course JSON."""
import argparse
import json
from pathlib import Path
from course_model import read_json, compile_course
from build_lesson import build


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--manifest', required=True, type=Path)
    p.add_argument('--course', required=True, type=Path)
    p.add_argument('--work-dir', required=True, type=Path)
    p.add_argument('--output', type=Path)
    p.add_argument('--compile-only', action='store_true')
    a = p.parse_args()
    if not a.compile_only and not a.output:
        p.error('--output is required unless --compile-only')
    data, source, report = compile_course(read_json(a.course), a.manifest)
    a.work_dir.mkdir(parents=True, exist_ok=True)
    (a.work_dir/'compiled-lesson.json').write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    (a.work_dir/'combined-source.txt').write_bytes(source.encode('utf-8'))
    (a.work_dir/'integration-check.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    if not a.compile_only:
        build(data, a.output, a.work_dir/'smartart')
    print(json.dumps({'compiled': str((a.work_dir/'compiled-lesson.json').resolve()), 'output': str(a.output.resolve()) if a.output else None, **report}, ensure_ascii=True))


if __name__ == '__main__':
    main()
