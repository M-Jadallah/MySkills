"""Deterministic Arabic RTL Word report builder for the arabic-daily-work-report skill."""
from __future__ import annotations

import argparse
import json
from datetime import date, datetime
from pathlib import Path
from typing import Any, Iterable

from docx import Document
from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT, WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor

NAVY = "1F4E79"
GOLD = "B89B5E"
LIGHT_BLUE = "EAF1F8"
LIGHT_GOLD = "F7F1E6"
GRID = "D9D9D9"
BLACK = "000000"
GRAY = "555555"
DIGITS = str.maketrans("0123456789", "٠١٢٣٤٥٦٧٨٩")
ARABIC_MONTHS = {
    1: "يناير", 2: "فبراير", 3: "مارس", 4: "أبريل", 5: "مايو", 6: "يونيو",
    7: "يوليو", 8: "أغسطس", 9: "سبتمبر", 10: "أكتوبر", 11: "نوفمبر", 12: "ديسمبر",
}


def arabic_digits(value: Any) -> str:
    return str(value).translate(DIGITS)


def display_date(value: str | None) -> str:
    if not value:
        return arabic_digits(date.today().strftime("%d-%m-%Y"))
    try:
        parsed = datetime.strptime(value, "%Y-%m-%d")
        return f"{arabic_digits(parsed.day)} {ARABIC_MONTHS[parsed.month]} {arabic_digits(parsed.year)}"
    except ValueError:
        return arabic_digits(value)


def as_text(value: Any) -> str:
    if isinstance(value, dict):
        return str(value.get("text", "")).strip()
    return str(value).strip()


def nonempty_items(value: Any) -> list[str]:
    if not value:
        return []
    if isinstance(value, str):
        return [value.strip()] if value.strip() else []
    return [as_text(item) for item in value if as_text(item)]


def set_cell_shading(cell, fill: str) -> None:
    tc_pr = cell._tc.get_or_add_tcPr()
    shd = tc_pr.find(qn("w:shd"))
    if shd is None:
        shd = OxmlElement("w:shd")
        tc_pr.append(shd)
    shd.set(qn("w:fill"), fill)
    shd.set(qn("w:val"), "clear")


def set_cell_border(cell, color: str = GRID, size: str = "6") -> None:
    tc_pr = cell._tc.get_or_add_tcPr()
    borders = tc_pr.first_child_found_in("w:tcBorders")
    if borders is None:
        borders = OxmlElement("w:tcBorders")
        tc_pr.append(borders)
    for edge in ("top", "left", "bottom", "right", "insideH", "insideV"):
        element = borders.find(qn(f"w:{edge}"))
        if element is None:
            element = OxmlElement(f"w:{edge}")
            borders.append(element)
        element.set(qn("w:val"), "single")
        element.set(qn("w:sz"), size)
        element.set(qn("w:space"), "0")
        element.set(qn("w:color"), color)


def set_cell_margins(cell, top: int = 100, start: int = 150, bottom: int = 100, end: int = 150) -> None:
    tc_pr = cell._tc.get_or_add_tcPr()
    margins = tc_pr.first_child_found_in("w:tcMar")
    if margins is None:
        margins = OxmlElement("w:tcMar")
        tc_pr.append(margins)
    for name, value in (("top", top), ("start", start), ("bottom", bottom), ("end", end)):
        node = margins.find(qn(f"w:{name}"))
        if node is None:
            node = OxmlElement(f"w:{name}")
            margins.append(node)
        node.set(qn("w:w"), str(value))
        node.set(qn("w:type"), "dxa")


def set_table_direction(table) -> None:
    tbl_pr = table._tbl.tblPr
    bidi = tbl_pr.find(qn("w:bidiVisual"))
    if bidi is None:
        bidi = OxmlElement("w:bidiVisual")
        tbl_pr.append(bidi)
    bidi.set(qn("w:val"), "1")


def set_paragraph_rtl(paragraph, alignment=WD_ALIGN_PARAGRAPH.RIGHT) -> None:
    paragraph.alignment = alignment
    p_pr = paragraph._p.get_or_add_pPr()
    bidi = p_pr.find(qn("w:bidi"))
    if bidi is None:
        bidi = OxmlElement("w:bidi")
        p_pr.append(bidi)
    bidi.set(qn("w:val"), "1")
    lang = p_pr.find(qn("w:lang"))
    if lang is None:
        lang = OxmlElement("w:lang")
        p_pr.append(lang)
    lang.set(qn("w:val"), "ar-SA")
    lang.set(qn("w:bidi"), "ar-SA")
    lang.set(qn("w:eastAsia"), "ar-SA")


def set_run_font(run, size: float = 13, bold: bool = False, color: str = BLACK, italic: bool = False) -> None:
    run.font.name = "Arial"
    r_pr = run._element.get_or_add_rPr()
    fonts = r_pr.rFonts
    if fonts is None:
        fonts = OxmlElement("w:rFonts")
        r_pr.append(fonts)
    for attr in ("ascii", "hAnsi", "cs"):
        fonts.set(qn(f"w:{attr}"), "Arial")
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.italic = italic
    run.font.color.rgb = RGBColor.from_string(color)
    rtl = r_pr.find(qn("w:rtl"))
    if rtl is None:
        rtl = OxmlElement("w:rtl")
        r_pr.append(rtl)
    rtl.set(qn("w:val"), "1")


def remove_paragraph_borders(target) -> None:
    element = target._p if hasattr(target, "_p") else target._element
    p_pr = element.get_or_add_pPr()
    borders = p_pr.find(qn("w:pBdr"))
    if borders is not None:
        p_pr.remove(borders)


def add_field(run, instruction: str) -> None:
    begin = OxmlElement("w:fldChar")
    begin.set(qn("w:fldCharType"), "begin")
    instr = OxmlElement("w:instrText")
    instr.set(qn("xml:space"), "preserve")
    instr.text = instruction
    end = OxmlElement("w:fldChar")
    end.set(qn("w:fldCharType"), "end")
    run._r.extend((begin, instr, end))


def add_page_border(section) -> None:
    sect_pr = section._sectPr
    borders = sect_pr.find(qn("w:pgBorders"))
    if borders is None:
        borders = OxmlElement("w:pgBorders")
        sect_pr.append(borders)
    borders.set(qn("w:offsetFrom"), "page")
    for edge in ("top", "left", "bottom", "right"):
        element = borders.find(qn(f"w:{edge}"))
        if element is None:
            element = OxmlElement(f"w:{edge}")
            borders.append(element)
        element.set(qn("w:val"), "single")
        element.set(qn("w:sz"), "18")
        element.set(qn("w:space"), "28")
        element.set(qn("w:color"), NAVY)


def add_footer(section, date_text: str) -> None:
    paragraph = section.footer.paragraphs[0]
    paragraph.paragraph_format.space_before = Pt(4)
    set_paragraph_rtl(paragraph, WD_ALIGN_PARAGRAPH.CENTER)
    run = paragraph.add_run(f"تقرير سير العمل اليومي  |  {date_text}  |  صفحة ")
    set_run_font(run, size=9, color=GRAY)
    page_run = paragraph.add_run()
    set_run_font(page_run, size=9, color=GRAY)
    add_field(page_run, "PAGE")


def configure_document(document: Document, date_text: str) -> None:
    section = document.sections[0]
    section.page_width = Inches(8.5)
    section.page_height = Inches(11)
    section.top_margin = Inches(0.72)
    section.bottom_margin = Inches(0.62)
    section.left_margin = Inches(0.78)
    section.right_margin = Inches(0.78)
    section.header_distance = Inches(0.3)
    section.footer_distance = Inches(0.3)
    add_page_border(section)
    add_footer(section, date_text)
    for style_name in ("Normal", "Title", "Heading 1", "Heading 2"):
        style = document.styles[style_name]
        style.font.name = "Arial"
        style._element.get_or_add_rPr().rFonts.set(qn("w:ascii"), "Arial")
        style._element.get_or_add_rPr().rFonts.set(qn("w:hAnsi"), "Arial")
        style._element.get_or_add_rPr().rFonts.set(qn("w:cs"), "Arial")
        style.font.color.rgb = RGBColor.from_string(BLACK)
        remove_paragraph_borders(style)
    document.styles["Normal"].font.size = Pt(13)
    document.styles["Normal"].paragraph_format.line_spacing = 1.25


def add_title(document: Document) -> None:
    paragraph = document.add_paragraph()
    paragraph.style = document.styles["Title"]
    remove_paragraph_borders(paragraph)
    paragraph.paragraph_format.space_after = Pt(5)
    paragraph.paragraph_format.line_spacing = 1.0
    set_paragraph_rtl(paragraph, WD_ALIGN_PARAGRAPH.CENTER)
    run = paragraph.add_run("تقرير سير العمل اليومي")
    set_run_font(run, size=22, bold=True)
    subtitle = document.add_paragraph()
    subtitle.paragraph_format.space_after = Pt(18)
    subtitle.paragraph_format.line_spacing = 1.1
    set_paragraph_rtl(subtitle, WD_ALIGN_PARAGRAPH.CENTER)
    run = subtitle.add_run("القرارات المتخذة والمقترحات والإجراءات التنظيمية")
    set_run_font(run, size=13, color=GRAY)


def add_metadata(document: Document, payload: dict[str, Any], date_text: str) -> None:
    table = document.add_table(rows=2, cols=4)
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.autofit = False
    set_table_direction(table)
    widths = [Inches(1.0), Inches(2.55), Inches(1.15), Inches(2.4)]
    values = [
        ("التاريخ", date_text, "الجهة", payload.get("recipient", "الإدارة")),
        ("الموضوع", payload.get("subject", "سير العمل والقرارات والإجراءات"), "النطاق", payload.get("scope", "الدوام والحلقات والموقع")),
    ]
    for row_index, row_values in enumerate(values):
        for col_index, value in enumerate(row_values):
            cell = table.cell(row_index, col_index)
            cell.width = widths[col_index]
            cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
            set_cell_margins(cell, 95, 120, 95, 120)
            set_cell_border(cell)
            set_cell_shading(cell, LIGHT_GOLD if col_index in (0, 2) else "FFFFFF")
            paragraph = cell.paragraphs[0]
            paragraph.paragraph_format.space_after = Pt(0)
            set_paragraph_rtl(paragraph, WD_ALIGN_PARAGRAPH.CENTER if col_index in (0, 2) else WD_ALIGN_PARAGRAPH.RIGHT)
            run = paragraph.add_run(str(value))
            set_run_font(run, size=10.5, bold=col_index in (0, 2))
    spacer = document.add_paragraph()
    spacer.paragraph_format.line_spacing = 0.25


def add_body(document: Document, text: str) -> None:
    paragraph = document.add_paragraph()
    paragraph.paragraph_format.space_after = Pt(6)
    paragraph.paragraph_format.line_spacing = 1.25
    paragraph.paragraph_format.first_line_indent = Inches(0.15)
    set_paragraph_rtl(paragraph)
    keep = OxmlElement("w:keepLines")
    paragraph._p.get_or_add_pPr().append(keep)
    run = paragraph.add_run(text)
    set_run_font(run)


def add_heading(document: Document, text: str) -> None:
    paragraph = document.add_paragraph()
    paragraph.style = document.styles["Heading 1"]
    paragraph.paragraph_format.space_before = Pt(12)
    paragraph.paragraph_format.space_after = Pt(5)
    paragraph.paragraph_format.line_spacing = 1.05
    set_paragraph_rtl(paragraph)
    keep = OxmlElement("w:keepNext")
    paragraph._p.get_or_add_pPr().append(keep)
    run = paragraph.add_run(text)
    set_run_font(run, size=15, bold=True)


def add_marker(document: Document) -> None:
    paragraph = document.add_paragraph()
    paragraph.paragraph_format.space_after = Pt(3)
    paragraph.paragraph_format.line_spacing = 0.2
    set_paragraph_rtl(paragraph)
    run = paragraph.add_run("◆")
    set_run_font(run, size=9, color=GOLD)


def add_item(document: Document, text: str, number: int) -> None:
    paragraph = document.add_paragraph()
    paragraph.paragraph_format.left_indent = Inches(0.1)
    paragraph.paragraph_format.right_indent = Inches(0.18)
    paragraph.paragraph_format.first_line_indent = Inches(-0.08)
    paragraph.paragraph_format.space_after = Pt(4)
    paragraph.paragraph_format.line_spacing = 1.2
    set_paragraph_rtl(paragraph)
    keep = OxmlElement("w:keepLines")
    paragraph._p.get_or_add_pPr().append(keep)
    marker = paragraph.add_run(f"\u200f{arabic_digits(number)}.\u200f ")
    set_run_font(marker, size=13, bold=True, color=NAVY)
    run = paragraph.add_run(text)
    set_run_font(run)


def add_section(document: Document, title: str, items: Iterable[str], description: str | None = None) -> None:
    entries = list(items)
    if not entries:
        return
    add_heading(document, title)
    add_marker(document)
    if description:
        add_body(document, description)
    for index, item in enumerate(entries, 1):
        add_item(document, item, index)


def harden_direction(document: Document) -> None:
    """Apply RTL metadata again after all content is assembled."""
    paragraphs = list(document.paragraphs)
    for table in document.tables:
        for row in table.rows:
            for cell in row.cells:
                paragraphs.extend(cell.paragraphs)
    for paragraph in paragraphs:
        set_paragraph_rtl(paragraph, paragraph.alignment or WD_ALIGN_PARAGRAPH.RIGHT)
        for run in paragraph.runs:
            r_pr = run._element.get_or_add_rPr()
            rtl = r_pr.find(qn("w:rtl"))
            if rtl is None:
                rtl = OxmlElement("w:rtl")
                r_pr.append(rtl)
            rtl.set(qn("w:val"), "1")


def normalize_payload(payload: dict[str, Any]) -> dict[str, Any]:
    sections = payload.get("sections", {})
    return {
        "report_date": payload.get("report_date"),
        "recipient": payload.get("recipient", "الإدارة"),
        "subject": payload.get("subject", "سير العمل والقرارات والإجراءات"),
        "scope": payload.get("scope", "الدوام والحلقات والموقع"),
        "intro": payload.get("intro"),
        "decisions": nonempty_items(payload.get("decisions", sections.get("decisions"))),
        "proposals": nonempty_items(payload.get("proposals", sections.get("proposals"))),
        "observations": nonempty_items(payload.get("observations", sections.get("observations"))),
        "teacher_problems": nonempty_items(payload.get("teacher_problems", sections.get("teacher_problems"))),
        "follow_up": nonempty_items(payload.get("follow_up", sections.get("follow_up"))),
        "summary": payload.get("summary"),
        "proposal_description": payload.get("proposal_description"),
        "problem_description": payload.get("problem_description"),
    }


def build(payload: dict[str, Any], output: Path) -> None:
    data = normalize_payload(payload)
    date_text = payload.get("report_date_display") or display_date(data["report_date"])
    document = Document()
    configure_document(document, date_text)
    add_title(document)
    add_metadata(document, data, date_text)
    intro = data["intro"] or "يستعرض هذا التقرير أبرز ما جرى خلال سير العمل اليوم، ويجمع القرارات والإجراءات التنظيمية والمقترحات المطروحة والمشكلات التي سجلها المعلمون، مع تحديد نقاط المتابعة اللازمة لاستكمال التنفيذ وتحسين الانضباط وسهولة المتابعة."
    add_body(document, intro)
    add_section(document, "أولًا  القرارات والإجراءات التنظيمية", data["decisions"])
    add_section(document, "ثانيًا  المقترحات المطروحة وإعادة توزيع المسؤوليات", data["proposals"], data["proposal_description"] or "تتضمن البنود الآتية مقترحات تنظيمية نوقشت خلال اليوم، وتحتاج إلى اعتمادها أو استكمال متطلباتها قبل التطبيق النهائي.")
    add_section(document, "ثالثًا  الملاحظات المتعلقة بالأداء والانضباط", data["observations"])
    add_section(document, "رابعًا  المشكلات المسجلة من المعلمين", data["teacher_problems"], data["problem_description"])
    add_section(document, "خامسًا  نقاط المتابعة", data["follow_up"], "لضمان انتقال ما نوقش إلى خطوات قابلة للمتابعة، تُدرج البنود الآتية ضمن أولويات العمل القادمة:")
    summary = data["summary"] or "يوثق هذا التقرير البنود التي وردت خلال سير العمل اليوم، ويحدد ما يحتاج إلى متابعة أو اعتماد في المرحلة التالية."
    add_heading(document, "خلاصة التقرير")
    add_marker(document)
    add_body(document, summary)
    harden_direction(document)
    document.core_properties.title = "تقرير سير العمل اليومي"
    document.core_properties.subject = data["subject"]
    document.core_properties.language = "ar-SA"
    output.parent.mkdir(parents=True, exist_ok=True)
    document.save(output)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build an Arabic RTL daily work report DOCX")
    parser.add_argument("--input", required=True, type=Path, help="UTF-8 JSON payload")
    parser.add_argument("--output", required=True, type=Path, help="Output DOCX path")
    args = parser.parse_args()
    with args.input.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    build(payload, args.output)
    print(args.output)


if __name__ == "__main__":
    main()
