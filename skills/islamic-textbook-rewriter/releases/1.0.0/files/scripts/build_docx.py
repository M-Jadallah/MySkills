"""Validate, build in a temporary file, inspect, then publish a complete DOCX."""
from __future__ import annotations

import argparse
import json
import os
import tempfile
from pathlib import Path

from lesson_docx.builder import build_lesson_docx
from lesson_docx.validate import validate_docx
from utils import load_json, normalize_lesson, safe_filename
from validate_input import validate_lesson_data


def build(data: dict, output_path: str | Path, *, draft: bool = False) -> dict:
    data = normalize_lesson(data)
    validation = validate_lesson_data(data, allow_draft=draft)
    report = {"ok": False, "built": False, "draft": draft, "input_errors": validation["errors"], "input_warnings": validation["warnings"], "input_stats": validation["stats"], "docx_errors": [], "docx_warnings": [], "smartart_failures": [], "smartart_success": 0}
    if not validation["ok"]:
        return report
    output = Path(output_path).resolve()
    if draft and not output.name.endswith(".draft.docx"):
        output = output.with_name(output.stem + ".draft.docx")
    output.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=".lesson-build-", suffix=".docx", dir=output.parent)
    os.close(fd)
    temporary = Path(temp_name)
    try:
        built = build_lesson_docx(data, temporary, draft=draft)
        report.update(section_count=built.section_count, smartart_success=built.smartart_success, smartart_failures=built.smartart_failures)
        errors, warnings = validate_docx(temporary, data)
        report.update(docx_errors=errors, docx_warnings=warnings)
        if not errors and not built.smartart_failures and built.smartart_success == validation["stats"]["concept_maps"]:
            os.replace(temporary, output)
            report.update(ok=not draft, built=True, output=str(output))
        else:
            report["docx_errors"].append("لم يُعتمد الناتج؛ يجب نجاح جميع الخرائط والفحوص")
    except Exception as exc:
        report["docx_errors"].append(f"تعذّر البناء: {exc}")
    finally:
        temporary.unlink(missing_ok=True)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True)
    parser.add_argument("--output")
    parser.add_argument("--draft", action="store_true", help="Write an explicitly named draft when the closing is unavailable")
    args = parser.parse_args()
    try:
        data = load_json(args.input)
        title = data.get("title", "lesson") if isinstance(data, dict) else "lesson"
        output = args.output or str(Path(args.input).resolve().parent / (safe_filename(title) + ".docx"))
        report = build(data, output, draft=args.draft)
    except Exception as exc:
        report = {"ok": False, "built": False, "input_errors": [f"تعذّر قراءة المدخل: {exc}"]}
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["ok"] else (2 if report.get("built") and report.get("draft") else 1)


if __name__ == "__main__":
    raise SystemExit(main())
