"""Check worker evidence, integrated course coverage and optional native DOCX."""
import argparse
import json
from pathlib import Path
from course_model import read_json, load_run, compile_course


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--manifest', required=True, type=Path)
    p.add_argument('--course', type=Path)
    p.add_argument('--docx', type=Path)
    p.add_argument('--report', required=True, type=Path)
    a = p.parse_args()
    try:
        if a.course:
            document, source, report = compile_course(read_json(a.course), a.manifest)
            if a.docx:
                from check_lesson import check
                document_report = check(document, a.docx, source)
                report['document'] = document_report
                if not document_report['passed_structural_checks']:
                    raise ValueError(json.dumps(document_report['errors'], ensure_ascii=False))
        else:
            if a.docx:
                p.error('--docx requires --course')
            _, sources, _, _, checks, _ = load_run(a.manifest)
            report = {'sources': len(sources), 'worker_checks': checks}
        report['passed'] = True
    except (ValueError, KeyError, TypeError, AttributeError, OSError) as exc:
        report = {'passed': False, 'error': str(exc)}
    a.report.parent.mkdir(parents=True, exist_ok=True)
    a.report.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(report, ensure_ascii=True, indent=2))
    raise SystemExit(0 if report['passed'] else 1)


if __name__ == '__main__':
    main()
