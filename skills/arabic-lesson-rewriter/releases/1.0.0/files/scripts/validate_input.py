"""Validate agent-authored lesson JSON BEFORE building the DOCX.

Errors block the build (structure violations, insufficient tashkeel).
Warnings are auto-fixed later by build_docx.py (ASCII digits, the full
salawat phrase, fixable tanween mistakes) and never block the delivery gate.

Usage:
    python scripts/validate_input.py --input lesson.json [--config config/default.json]

Prints a JSON report {ok, errors, warnings, stats}; exit 0 when ok, else 1.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

from arabic_text import fix_tanween_errors, strip_tashkeel, tashkeel_coverage_ratio
from utils import load_json

SCRIPTS_DIR = Path(__file__).resolve().parent
DEFAULT_CONFIG = SCRIPTS_DIR.parent / "config" / "default.json"

BLOCK_TYPES = {"paragraph", "evidence", "bullet_list", "numbered_list"}
ASCII_DIGITS = set("0123456789")
SALAWAT_PLAIN = strip_tashkeel("صلى الله عليه وسلم")
_ARABIC_LETTER_RE = re.compile(r"[\u0621-\u063A\u0641-\u064A]")  # base letters, no tatweel/marks

DEFAULT_CONFIG_VALUES = {
    "tashkeel": {
        "min_letters_for_check": 6,
        "min_ratio_headings_labels": 0.5,
        "min_ratio_long_text": 0.35,
    },
    "concept_map": {"max_depth": 6, "label_max_codepoints": 160},
}


def _load_config(path: str | None) -> dict[str, Any]:
    if not path:
        path = str(DEFAULT_CONFIG)
    config_path = Path(path)
    merged = {
        "tashkeel": dict(DEFAULT_CONFIG_VALUES["tashkeel"]),
        "concept_map": dict(DEFAULT_CONFIG_VALUES["concept_map"]),
    }
    if not config_path.exists():
        return merged
    config = load_json(config_path)
    for key in ("tashkeel", "concept_map"):
        if isinstance(config.get(key), dict):
            merged[key].update(config[key])
    return merged


class _Report:
    def __init__(self) -> None:
        self.errors: list[str] = []
        self.warnings: list[str] = []
        self.stats = {"sections": 0, "blocks": 0, "evidence_blocks": 0, "tables": 0, "concept_maps": 0}

    def error(self, message: str) -> None:
        self.errors.append(message)

    def warning(self, message: str) -> None:
        self.warnings.append(message)


def _check_text(text: Any, ctx: str, rep: _Report, *, min_ratio: float, config: dict[str, Any]) -> None:
    if not isinstance(text, str):
        rep.error(f"{ctx}: يجب أن يكون نصًا (وجدنا {type(text).__name__})")
        return
    if not text.strip():
        rep.error(f"{ctx}: نص فارغ")
        return

    plain = strip_tashkeel(text)
    if len(_ARABIC_LETTER_RE.findall(plain)) >= config["tashkeel"]["min_letters_for_check"]:
        ratio = tashkeel_coverage_ratio(text)
        if ratio < min_ratio:
            rep.error(f"{ctx}: التشكيل غير كافٍ (النسبة {ratio:.2f} < {min_ratio}) — شكِّل النص تشكيلًا كاملًا")

    if ASCII_DIGITS & set(text):
        rep.warning(f"{ctx}: يحوي أرقامًا إنجليزية — ستُحوَّل تلقائيًا إلى أرقام عربية عند البناء")
    if SALAWAT_PLAIN in plain:
        rep.warning(f"{ctx}: عبارة الصلاة الكاملة يجب أن تُكتب برمز ﷺ — ستُستبدل تلقائيًا عند البناء")
    if fix_tanween_errors(text) != text:
        rep.warning(f"{ctx}: تنوين غير صحيح — سيُصحَّح تلقائيًا عند البناء")


def _check_blocks(blocks: Any, ctx: str, rep: _Report, config: dict[str, Any]) -> None:
    if not isinstance(blocks, list):
        rep.error(f"{ctx}: يجب أن تكون قائمة بلوكات")
        return
    for i, block in enumerate(blocks):
        bctx = f"{ctx}[{i}]"
        if not isinstance(block, dict):
            rep.error(f"{bctx}: يجب أن يكون كائنًا فيه type")
            continue
        kind = block.get("type")
        if kind not in BLOCK_TYPES:
            rep.error(f"{bctx}: نوع بلوك غير معروف {kind!r} — المسموح: {sorted(BLOCK_TYPES)}")
            continue
        rep.stats["blocks"] += 1
        if kind == "evidence":
            rep.stats["evidence_blocks"] += 1
            _check_text(block.get("text"), f"{bctx}.text", rep, min_ratio=config["tashkeel"]["min_ratio_long_text"], config=config)
        elif kind == "paragraph":
            _check_text(block.get("text"), f"{bctx}.text", rep, min_ratio=config["tashkeel"]["min_ratio_long_text"], config=config)
        else:  # bullet_list / numbered_list
            items = block.get("items")
            if not isinstance(items, list) or not items:
                rep.error(f"{bctx}: قائمة {kind} تحتاج items غير فارغة")
                continue
            for j, item in enumerate(items):
                _check_text(item, f"{bctx}.items[{j}]", rep, min_ratio=config["tashkeel"]["min_ratio_long_text"], config=config)


def _check_concept_map(node: Any, ctx: str, rep: _Report, config: dict[str, Any], depth: int = 0) -> None:
    if depth > config["concept_map"].get("max_depth", 6):
        rep.error(f"{ctx}: عمق الخريطة يتجاوز الحد ({config['concept_map'].get('max_depth', 6)})")
        return
    if not isinstance(node, dict):
        rep.error(f"{ctx}: يجب أن يكون كائنًا فيه label وchildren")
        return
    label = node.get("label")
    _check_text(label, f"{ctx}.label", rep, min_ratio=config["tashkeel"]["min_ratio_headings_labels"], config=config)
    if isinstance(label, str) and len(label) > config["concept_map"]["label_max_codepoints"]:
        rep.error(f"{ctx}.label: تجاوز الطول الأقصى ({len(label)} > {config["concept_map"]["label_max_codepoints"]} حرفًا)")
    children = node.get("children")
    if not isinstance(children, list) or not children:
        rep.error(f"{ctx}: تحتاج children غير فارغة")
        return
    for i, child in enumerate(children):
        if isinstance(child, dict):
            _check_concept_map(child, f"{ctx}.children[{i}]", rep, config, depth + 1)
        else:
            _check_text(child, f"{ctx}.children[{i}]", rep, min_ratio=config["tashkeel"]["min_ratio_headings_labels"], config=config)


def _check_table(table: Any, ctx: str, rep: _Report, config: dict[str, Any]) -> None:
    if not isinstance(table, dict):
        rep.error(f"{ctx}: يجب أن يكون كائنًا فيه headers وrows")
        return
    headers = table.get("headers")
    if not isinstance(headers, list) or not headers or not all(isinstance(h, str) and h.strip() for h in headers):
        rep.error(f"{ctx}.headers: يجب أن تكون قائمة غير فارغة من نصوص")
        return
    rep.stats["tables"] += 1
    if table.get("title"):
        _check_text(table["title"], f"{ctx}.title", rep, min_ratio=config["tashkeel"]["min_ratio_headings_labels"], config=config)
    for i, header in enumerate(headers):
        _check_text(header, f"{ctx}.headers[{i}]", rep, min_ratio=config["tashkeel"]["min_ratio_headings_labels"], config=config)
    rows = table.get("rows", [])
    if not isinstance(rows, list):
        rep.error(f"{ctx}.rows: يجب أن تكون قائمة")
        return
    for i, row in enumerate(rows):
        if not isinstance(row, list) or not all(isinstance(cell, str) for cell in row):
            rep.error(f"{ctx}.rows[{i}]: يجب أن تكون قائمة خلايا نصية")
            continue
        if len(row) > len(headers):
            rep.error(f"{ctx}.rows[{i}]: عدد الخلايا ({len(row)}) أكبر من عدد الأعمدة ({len(headers)})")
            continue
        for j, cell in enumerate(row):
            if cell.strip():
                _check_text(cell, f"{ctx}.rows[{i}][{j}]", rep, min_ratio=config["tashkeel"]["min_ratio_headings_labels"], config=config)


def _check_section(section: Any, ctx: str, rep: _Report, config: dict[str, Any]) -> None:
    if not isinstance(section, dict):
        rep.error(f"{ctx}: يجب أن يكون كائنًا")
        return
    rep.stats["sections"] += 1
    _check_text(section.get("heading"), f"{ctx}.heading", rep, min_ratio=config["tashkeel"]["min_ratio_headings_labels"], config=config)
    _check_blocks(section.get("blocks", []), f"{ctx}.blocks", rep, config)

    subsections = section.get("subsections", [])
    if not isinstance(subsections, list):
        rep.error(f"{ctx}.subsections: يجب أن تكون قائمة")
        return
    for i, sub in enumerate(subsections):
        sctx = f"{ctx}.subsections[{i}]"
        if not isinstance(sub, dict):
            rep.error(f"{sctx}: يجب أن يكون كائنًا")
            continue
        _check_text(sub.get("heading"), f"{sctx}.heading", rep, min_ratio=config["tashkeel"]["min_ratio_headings_labels"], config=config)
        level = sub.get("level", 2)
        if not isinstance(level, int) or level < 2:
            rep.error(f"{sctx}.level: يجب أن يكون عددًا صحيحًا ≥ 2 (وجدنا {level!r})")
        _check_blocks(sub.get("blocks", []), f"{sctx}.blocks", rep, config)
        _check_section_subsections(sub, sctx, rep, config)

    if section.get("section_summary"):
        _check_text(section["section_summary"], f"{ctx}.section_summary", rep, min_ratio=config["tashkeel"]["min_ratio_headings_labels"], config=config)

    if section.get("table"):
        _check_table(section["table"], f"{ctx}.table", rep, config)
    if section.get("concept_map"):
        rep.stats["concept_maps"] += 1
        _check_concept_map(section["concept_map"], f"{ctx}.concept_map", rep, config)


def _check_section_subsections(section: dict[str, Any], ctx: str, rep: _Report, config: dict[str, Any]) -> None:
    for i, sub in enumerate(section.get("subsections", [])):
        if isinstance(sub, dict) and sub.get("subsections"):
            _check_section_subsections(sub, f"{ctx}.subsections[{i}]", rep, config)


def validate_lesson_data(data: Any, config: dict[str, Any] | None = None) -> dict[str, Any]:
    """Validate a lesson-data dict; returns {ok, errors, warnings, stats}."""
    rep = _Report()
    config = config or _load_config(None)

    if not isinstance(data, dict):
        rep.error("الجذر: يجب أن يكون كائن JSON")
    else:
        _check_text(data.get("title"), "title", rep, min_ratio=config["tashkeel"]["min_ratio_headings_labels"], config=config)
        if data.get("subtitle"):
            _check_text(data["subtitle"], "subtitle", rep, min_ratio=config["tashkeel"]["min_ratio_headings_labels"], config=config)
        sections = data.get("sections")
        if not isinstance(sections, list) or not sections:
            rep.error("sections: يجب أن تكون قائمة محاور غير فارغة")
        else:
            for i, section in enumerate(sections):
                _check_section(section, f"sections[{i}]", rep, config)

    return {"ok": not rep.errors, "errors": rep.errors, "warnings": rep.warnings, "stats": rep.stats}


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate lesson JSON before building the DOCX.")
    parser.add_argument("--input", required=True, help="path to lesson.json")
    parser.add_argument("--config", default=None, help="path to config JSON (default: config/default.json)")
    args = parser.parse_args()

    try:
        data = load_json(args.input)
    except Exception as exc:  # noqa: BLE001 - report any load failure as a validation error
        print(json.dumps({"ok": False, "errors": [f"تعذّر قراءة الملف: {exc}"], "warnings": [], "stats": {}}, ensure_ascii=False, indent=2))
        return 1

    report = validate_lesson_data(data, _load_config(args.config))
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
