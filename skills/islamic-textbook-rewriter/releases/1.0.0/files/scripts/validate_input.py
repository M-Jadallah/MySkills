"""Validate structure and audit-record completeness, never religious authenticity."""
from __future__ import annotations

import argparse
import json
import re
from datetime import date
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from arabic_text import LETTER, tashkeel_coverage_ratio
from utils import load_json

SOURCE_TYPES = {"quran", "hadith", "book", "history", "grading"}
METHODS = {
    "quran_text": {"quran"},
    "sahih_collection": {"sahih"},
    "scholar_grading": {"sahih", "hasan"},
    "historical_authentication": {"established"},
    "primary_text": {"attribution_verified"},
}


class Validator:
    def __init__(self, allow_draft: bool = False):
        self.allow_draft = allow_draft
        self.errors: list[str] = []
        self.warnings: list[str] = []
        self.sources: dict[str, dict] = {}
        self.stats = {"top_level_sections": 0, "sections": 0, "blocks": 0, "evidence_blocks": 0, "tables": 0, "concept_maps": 0}

    def fail(self, ctx: str, message: str) -> None:
        self.errors.append(f"{ctx}: {message}")

    def obj(self, value: Any, ctx: str, allowed: set[str]) -> bool:
        if not isinstance(value, dict):
            self.fail(ctx, "يجب أن يكون كائنًا")
            return False
        extras = set(value) - allowed
        if extras:
            self.fail(ctx, "حقول غير مدعومة: " + ", ".join(sorted(extras)))
        return True

    def text(self, value: Any, ctx: str, *, shaped: bool = True, short: bool = False) -> bool:
        if not isinstance(value, str) or not value.strip():
            self.fail(ctx, "يجب أن يكون نصًا غير فارغ")
            return False
        if shaped and len(LETTER.findall(value)) >= 3:
            threshold = 0.50 if short else 0.40
            ratio = tashkeel_coverage_ratio(value)
            if ratio < threshold:
                self.fail(ctx, f"كثافة التشكيل قليلة ({ratio:.2f} < {threshold:.2f})؛ راجع التشكيل الكامل")
        return True

    def source_list(self, items: Any) -> None:
        if not isinstance(items, list) or (not items and not self.allow_draft):
            self.fail("sources", "تحتاج قائمة مصادر غير فارغة")
            return
        for i, source in enumerate(items):
            ctx = f"sources[{i}]"
            if not self.obj(source, ctx, {"id", "type", "title", "author", "locator", "edition", "url", "local_path"}):
                continue
            sid = source.get("id")
            if not isinstance(sid, str) or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]*", sid):
                self.fail(ctx + ".id", "معرّف لاتيني مطلوب")
            elif sid in self.sources:
                self.fail(ctx + ".id", "معرّف مصدر مكرر")
            else:
                self.sources[sid] = source
            if source.get("type") not in SOURCE_TYPES:
                self.fail(ctx + ".type", "نوع مصدر غير معروف")
            for key in ("title", "locator"):
                self.text(source.get(key), ctx + "." + key, shaped=False)
            if source.get("type") in {"book", "history", "grading"}:
                self.text(source.get("author"), ctx + ".author", shaped=False)
            elif "author" in source:
                self.text(source["author"], ctx + ".author", shaped=False)
            if "edition" in source:
                self.text(source["edition"], ctx + ".edition", shaped=False)
            url, local = source.get("url"), source.get("local_path")
            if not url and not local:
                self.fail(ctx, "يلزم رابط مباشر أو مسار نسخة محلية")
            if url is not None:
                try:
                    parsed = urlsplit(url) if isinstance(url, str) else None
                    valid = parsed is not None and parsed.scheme in {"http", "https"} and bool(parsed.netloc) and not any(ch.isspace() for ch in url)
                except ValueError:
                    valid = False
                if not valid:
                    self.fail(ctx + ".url", "رابط HTTP(S) صحيح مطلوب")
            if local is not None:
                if not isinstance(local, str) or not Path(local).is_absolute() or not Path(local).is_file():
                    self.fail(ctx + ".local_path", "مسار مطلق لملف موجود مطلوب")

    def ref(self, sid: Any, ctx: str) -> bool:
        if not isinstance(sid, str) or sid not in self.sources:
            self.fail(ctx, "المصدر غير موجود في sources")
            return False
        return True

    def blocks(self, blocks: Any, ctx: str, *, allow_empty: bool = False) -> None:
        if not isinstance(blocks, list) or (not blocks and not allow_empty):
            self.fail(ctx, "قائمة بلوكات غير فارغة مطلوبة")
            return
        for i, block in enumerate(blocks):
            bctx = f"{ctx}[{i}]"
            if not isinstance(block, dict):
                self.fail(bctx, "بلوك غير صالح")
                continue
            kind = block.get("type")
            self.stats["blocks"] += 1
            if kind == "paragraph":
                self.obj(block, bctx, {"type", "text"})
                self.text(block.get("text"), bctx + ".text")
            elif kind in {"bullet_list", "numbered_list"}:
                self.obj(block, bctx, {"type", "items"})
                items = block.get("items")
                if not isinstance(items, list) or not items:
                    self.fail(bctx + ".items", "قائمة عناصر غير فارغة مطلوبة")
                else:
                    for j, item in enumerate(items):
                        self.text(item, f"{bctx}.items[{j}]")
                        if isinstance(item, str) and re.match(r"^\s*(?:[•●▪]|[0-9٠-٩]+[.)])\s*", item):
                            self.fail(f"{bctx}.items[{j}]", "لا تكتب علامة التعداد يدويًا")
            elif kind == "evidence":
                self.obj(block, bctx, {"type", "kind", "text", "source_id", "citation", "note"})
                self.stats["evidence_blocks"] += 1
                if block.get("kind") not in {"quran", "hadith", "athar", "scholar_quote"}:
                    self.fail(bctx + ".kind", "نوع الدليل غير معروف")
                self.text(block.get("text"), bctx + ".text")
                self.text(block.get("citation"), bctx + ".citation", shaped=False)
                if "note" in block:
                    self.text(block["note"], bctx + ".note", shaped=False)
                if self.ref(block.get("source_id"), bctx + ".source_id"):
                    stype = self.sources[block["source_id"]].get("type")
                    expected = {"quran": {"quran"}, "hadith": {"hadith"}, "athar": {"hadith", "book", "history"}, "scholar_quote": {"book"}}
                    if block.get("kind") in expected and stype not in expected[block["kind"]]:
                        self.fail(bctx + ".source_id", "نوع المصدر لا يناسب نوع الدليل")
            else:
                self.fail(bctx + ".type", "نوع بلوك غير مدعوم")

    def concept_map(self, root: Any, ctx: str) -> None:
        self.stats["concept_maps"] += 1
        count = 0

        def visit(node: Any, where: str, depth: int, is_root: bool = False) -> None:
            nonlocal count
            count += 1
            if depth > 6:
                self.fail(where, "عمق الخريطة يتجاوز ست حواف")
                return
            if isinstance(node, str) and not is_root:
                label, children = node, []
            elif self.obj(node, where, {"label", "children"}):
                label, children = node.get("label"), node.get("children", [])
            else:
                return
            if self.text(label, where + ".label", short=True):
                if len(label) > 160:
                    self.fail(where + ".label", "طول العقدة يتجاوز ١٦٠ نقطة Unicode")
                if not 1 <= len(label.split()) <= 7:
                    self.fail(where + ".label", "تحتاج العقدة من كلمة إلى سبع كلمات")
            if not isinstance(children, list) or (is_root and not children):
                self.fail(where + ".children", "قائمة أبناء مطلوبة؛ الجذر له أبناء")
                return
            for j, child in enumerate(children):
                visit(child, f"{where}.children[{j}]", depth + 1)

        visit(root, ctx, 0, True)
        if count > 15:
            self.warnings.append(f"{ctx}: {count} عقدة؛ راجع ازدحام الرسم وقسّمه عند الحاجة")

    def table(self, table: Any, ctx: str) -> None:
        if not self.obj(table, ctx, {"title", "headers", "rows"}):
            return
        self.stats["tables"] += 1
        if "title" in table:
            self.text(table["title"], ctx + ".title", short=True)
        headers, rows = table.get("headers"), table.get("rows")
        if not isinstance(headers, list) or not headers:
            self.fail(ctx + ".headers", "قائمة أعمدة غير فارغة مطلوبة")
            return
        for i, header in enumerate(headers):
            self.text(header, f"{ctx}.headers[{i}]", short=True)
        if not isinstance(rows, list) or not rows:
            self.fail(ctx + ".rows", "قائمة صفوف غير فارغة مطلوبة")
            return
        for i, row in enumerate(rows):
            if not isinstance(row, list) or len(row) != len(headers):
                self.fail(f"{ctx}.rows[{i}]", "عدد الخلايا يجب أن يساوي الأعمدة بالضبط")
                continue
            for j, cell in enumerate(row):
                self.text(cell, f"{ctx}.rows[{i}][{j}]")

    def section(self, node: Any, ctx: str, depth: int = 0) -> None:
        if depth > 2:
            self.fail(ctx, "الحد مستويان فرعيان تحت المحور الرئيسي؛ أعد توزيع المحاور")
            return
        if not self.obj(node, ctx, {"heading", "blocks", "subsections", "table", "concept_map", "map_policy", "map_omission_reason"}):
            return
        self.stats["sections"] += 1
        self.text(node.get("heading"), ctx + ".heading", short=True)
        children = node.get("subsections", [])
        has_children = isinstance(children, list) and bool(children)
        self.blocks(node.get("blocks"), ctx + ".blocks", allow_empty=has_children)
        if not isinstance(children, list):
            self.fail(ctx + ".subsections", "قائمة محاور فرعية مطلوبة")
        else:
            for i, child in enumerate(children):
                self.section(child, f"{ctx}.subsections[{i}]", depth + 1)
        if "table" in node:
            self.table(node["table"], ctx + ".table")
        policy = node.get("map_policy")
        if policy == "branching":
            if "concept_map" not in node:
                self.fail(ctx, "المحتوى المتفرع يحتاج concept_map")
            else:
                self.concept_map(node["concept_map"], ctx + ".concept_map")
            if "map_omission_reason" in node:
                self.fail(ctx, "سبب ترك الخريطة يناقض وجود المحتوى المتفرع")
        elif policy == "linear":
            self.text(node.get("map_omission_reason"), ctx + ".map_omission_reason", shaped=False)
            if "concept_map" in node:
                self.fail(ctx, "إذا كان له خريطة فاجعل map_policy هو branching")
        else:
            self.fail(ctx + ".map_policy", "يجب تحديد branching أو linear")

    def closing(self, closing: Any) -> None:
        ctx = "closing"
        if closing is None and self.allow_draft:
            self.warnings.append("الخاتمة غير مكتملة؛ الناتج مسودة")
            return
        if not self.obj(closing, ctx, {"kind", "heading", "blocks", "takeaway", "presentation", "verification"}):
            return
        if closing.get("kind") not in {"story", "admonition"}:
            self.fail(ctx + ".kind", "تحتاج story أو admonition")
        self.text(closing.get("heading"), ctx + ".heading", short=True)
        self.blocks(closing.get("blocks"), ctx + ".blocks")
        self.text(closing.get("takeaway"), ctx + ".takeaway")
        presentation = closing.get("presentation")
        if presentation not in {"paraphrase", "verbatim"}:
            self.fail(ctx + ".presentation", "تحتاج paraphrase أو verbatim")
        if presentation == "verbatim" and isinstance(closing.get("blocks"), list):
            if any(not isinstance(b, dict) or b.get("type") != "evidence" for b in closing["blocks"]):
                self.fail(ctx + ".blocks", "النقل الحرفي في evidence؛ الشرح في takeaway")
        v = closing.get("verification")
        vctx = ctx + ".verification"
        if not self.obj(v, vctx, {"status", "method", "verdict", "basis", "source_ids", "checked_at", "source_excerpt", "reviewer", "grading_source_id"}):
            return
        if v.get("status") != "verified":
            self.fail(vctx + ".status", "يجب إتمام التحقق الفعلي قبل اعتماد الخاتمة")
        method, verdict = v.get("method"), v.get("verdict")
        if method not in METHODS or verdict not in METHODS.get(method, set()):
            self.fail(vctx, "طريقة التحقق وحكمه غير متسقين")
        if closing.get("kind") == "story" and method == "primary_text":
            self.fail(vctx, "نسبة الحكاية إلى كتاب لا تثبت وقوعها؛ اختر خبرًا ثابتًا أو موعظة")
        for key in ("basis", "source_excerpt"):
            self.text(v.get(key), vctx + "." + key, shaped=False)
        try:
            raw_date = v.get("checked_at")
            if not isinstance(raw_date, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", raw_date):
                raise ValueError
            date.fromisoformat(raw_date)
        except (TypeError, ValueError):
            self.fail(vctx + ".checked_at", "تاريخ YYYY-MM-DD صحيح مطلوب")
        ids = v.get("source_ids")
        if not isinstance(ids, list) or not ids:
            self.fail(vctx + ".source_ids", "مصادر التحقق مطلوبة")
            ids = []
        for i, sid in enumerate(ids):
            self.ref(sid, f"{vctx}.source_ids[{i}]")
        types = {self.sources[sid].get("type") for sid in ids if isinstance(sid, str) and sid in self.sources}
        expected = {"quran_text": "quran", "sahih_collection": "hadith", "scholar_grading": "hadith", "historical_authentication": "history", "primary_text": "book"}
        if method in expected and expected[method] not in types:
            self.fail(vctx + ".source_ids", "السجل لا يحوي مصدر النص الأصلي المناسب لطريقة التحقق")
        if method in {"scholar_grading", "historical_authentication"}:
            self.text(v.get("reviewer"), vctx + ".reviewer", shaped=False)
            grade_id = v.get("grading_source_id")
            if self.ref(grade_id, vctx + ".grading_source_id"):
                if grade_id not in ids or self.sources[grade_id].get("type") != "grading":
                    self.fail(vctx + ".grading_source_id", "مرجع الحكم يجب أن يكون من نوع grading وضمن source_ids")


def validate_lesson_data(data: Any, *, allow_draft: bool = False) -> dict[str, Any]:
    v = Validator(allow_draft)
    if v.obj(data, "root", {"title", "subtitle", "sources", "overview_map", "sections", "closing", "editorial_notes"}):
        v.text(data.get("title"), "title", short=True)
        if "subtitle" in data:
            v.text(data["subtitle"], "subtitle", short=True)
        v.source_list(data.get("sources"))
        if "editorial_notes" in data:
            notes = data["editorial_notes"]
            if not isinstance(notes, list):
                v.fail("editorial_notes", "قائمة ملاحظات مطلوبة")
            else:
                for i, note in enumerate(notes):
                    v.text(note, f"editorial_notes[{i}]", shaped=False)
        sections = data.get("sections")
        if not isinstance(sections, list) or not sections:
            v.fail("sections", "قائمة محاور غير فارغة مطلوبة")
        else:
            v.stats["top_level_sections"] = len(sections)
            for i, node in enumerate(sections):
                v.section(node, f"sections[{i}]")
            if len(sections) > 1 and "overview_map" not in data:
                v.fail("overview_map", "الدرس متعدد المحاور يحتاج خريطة عامة")
        if "overview_map" in data:
            v.concept_map(data["overview_map"], "overview_map")
        v.closing(data.get("closing"))
    return {"ok": not v.errors, "errors": v.errors, "warnings": v.warnings, "stats": v.stats}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True)
    parser.add_argument("--draft", action="store_true", help="Allow a missing closing, never an unverified story")
    args = parser.parse_args()
    try:
        report = validate_lesson_data(load_json(args.input), allow_draft=args.draft)
    except Exception as exc:
        report = {"ok": False, "errors": [f"تعذّر التحقق: {exc}"], "warnings": [], "stats": {}}
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
