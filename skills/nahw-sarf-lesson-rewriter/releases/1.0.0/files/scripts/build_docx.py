"""Build the lesson DOCX from agent-authored lesson JSON.

Pipeline: load JSON -> normalize every text field (salawat/tanween/digits,
idempotent) -> validate input (structure + tashkeel gate) -> build the DOCX
(incl. real SmartArt injection) -> validate the produced file -> print a
single JSON report. No output file is produced when input validation fails.

Usage:
    python scripts/build_docx.py --input lesson.json --output lessons_output/<name>.docx

Exit 0 only when the whole report is clean (input errors = 0, docx errors = 0).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from lesson_docx.builder import build_lesson_docx
from lesson_docx.validate import validate_docx
from utils import deep_normalize, load_json, safe_filename
from validate_input import _load_config, validate_lesson_data


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the lesson DOCX from lesson JSON.")
    parser.add_argument("--input", required=True, help="path to lesson.json")
    parser.add_argument("--output", default=None, help="output .docx path (default: <safe title>.docx next to the input)")
    args = parser.parse_args()

    try:
        data = deep_normalize(load_json(args.input))
    except Exception as exc:  # noqa: BLE001 - report any load failure as an input error
        print(json.dumps({"ok": False, "input_errors": [f"تعذّر قراءة الملف: {exc}"], "built": False}, ensure_ascii=False, indent=2))
        return 1

    input_report = validate_lesson_data(data, _load_config(None))
    if not input_report["ok"]:
        print(json.dumps(
            {
                "ok": False,
                "built": False,
                "input_errors": input_report["errors"],
                "input_warnings": input_report["warnings"],
                "hint": "أصلح أخطاء lesson.json أعلاه ثم أعد البناء",
            },
            ensure_ascii=False,
            indent=2,
        ))
        return 1

    title = data.get("title") if isinstance(data, dict) else None
    output_path = Path(args.output) if args.output else Path(args.input).resolve().parent / f"{safe_filename(title or '')}.docx"

    build_report = build_lesson_docx(data, output_path)
    docx_errors, docx_warnings = validate_docx(output_path)

    report = {
        "ok": not docx_errors,
        "built": True,
        "output": str(build_report.output_path),
        "section_count": build_report.section_count,
        "smartart_success": build_report.smartart_success,
        "smartart_failures": build_report.smartart_failures,
        "input_warnings": input_report["warnings"],
        "input_stats": input_report["stats"],
        "docx_errors": docx_errors,
        "docx_warnings": docx_warnings,
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
