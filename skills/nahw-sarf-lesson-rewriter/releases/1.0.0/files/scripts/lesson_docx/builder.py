from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from docx.oxml import parse_xml
from docx.oxml.ns import nsdecls, qn

from . import smartart
from .styles import BLACK, BROWN, GREEN, GREEN_LIGHT, add_para, add_text_runs, arabic_indic_digits, add_heading, get_or_add, set_list_indent, set_paragraph_rtl, setup_document, shade_paragraph
from .tables import add_styled_table

logger = logging.getLogger(__name__)


@dataclass
class BuildReport:
    output_path: Path
    section_count: int
    smartart_success: int
    smartart_failures: list[dict[str, str]] = field(default_factory=list)


def _add_blocks(doc, blocks: list[dict[str, Any]]) -> None:
    for block in blocks:
        kind = block.get("type")
        if kind == "paragraph":
            add_para(doc, block["text"], size=22, color=BLACK, after=160)
        elif kind == "evidence":
            # بيت الألفية فقط: بلوك أخضر مميز بتنسيق شعري مركزي. الشطران
            # يُكتبان مفصولين بـ «…» ويُعرضان في سطر واحد متمركز بخط أخضر
            # غامق عريض على تظليل أخضر فاتح، مع إزاحة جانبية تُبرز البيت.
            text = block["text"].strip()
            if text.startswith("«") and text.endswith("»"):
                text = text[1:-1].strip()
            hemistichs = [h.strip() for h in text.split("…") if h.strip()]
            verse = " … ".join(hemistichs) if len(hemistichs) > 1 else text
            p = doc.add_paragraph()
            set_paragraph_rtl(p, align="center", before=120, after=200)
            ind = get_or_add(p._p.get_or_add_pPr(), "w:ind")
            ind.set(qn("w:right"), "480")
            ind.set(qn("w:left"), "480")
            add_text_runs(p, verse, size=22, color=GREEN, bold=True)
            shade_paragraph(p, GREEN_LIGHT)
        elif kind == "bullet_list":
            items = block.get("items", [])
            for i, item in enumerate(items):
                p = add_para(doc, f"• {item}", size=22, color=BLACK, before=40 if i == 0 else 0, after=140 if i == len(items) - 1 else 70)
                set_list_indent(p)
        elif kind == "numbered_list":
            items = block.get("items", [])
            for i, item in enumerate(items, 1):
                number = arabic_indic_digits(str(i))
                p = add_para(doc, f"{number}. {item}", size=22, color=BLACK, before=40 if i == 1 else 0, after=140 if i == len(items) else 70)
                set_list_indent(p)


def _enqueue_concept_map(doc, tree: dict[str, Any], node_heading: str, smartart_jobs: list[tuple[int, dict[str, Any], str]]) -> None:
    # No caption is written above the diagram (per this skill's spec). The
    # empty spacer paragraph anchors the placeholder directly after the last
    # content element - even a table - and keeps a little breathing room.
    add_para(doc, "", size=8, before=160, after=40, keep_next=True)
    placeholder_p = parse_xml(
        smartart.make_placeholder_paragraph_xml(len(smartart_jobs) + 1)
        .replace("<w:p>", f"<w:p {nsdecls('w')}>", 1)
    )
    doc.paragraphs[-1]._p.addnext(placeholder_p)
    smartart_jobs.append((len(smartart_jobs) + 1, tree, node_heading))


def _render_node(doc, node: dict[str, Any], *, level: int, smartart_jobs: list[tuple[int, dict[str, Any], str]]) -> None:
    """Render a section (level=1) or any nested subsection - same shape:
    heading, blocks, nested subsections, summary, table, concept map."""
    add_heading(doc, node["heading"], level=level)
    _add_blocks(doc, node.get("blocks", []))
    for sub in node.get("subsections", []):
        _render_node(doc, sub, level=sub.get("level", 2), smartart_jobs=smartart_jobs)
    if node.get("section_summary"):
        _add_section_summary(doc, node["section_summary"])
    table = node.get("table")
    if table and table.get("headers"):
        add_styled_table(doc, table.get("title") or "جَدْوَلٌ تَوْضِيحِيٌّ", table["headers"], table.get("rows") or [])
    if node.get("concept_map"):
        _enqueue_concept_map(doc, node["concept_map"], node["heading"], smartart_jobs)


def _add_section_summary(doc, summary_text: str) -> None:
    add_para(doc, "◆ خُلَاصَةُ القِسْمِ", size=18, color=BROWN, bold=True, before=100, after=30, keep_next=True)
    add_para(doc, summary_text, size=22, color=BLACK, bold=True, after=100)


def build_lesson_docx(data: dict[str, Any], output_path: str | Path) -> BuildReport:
    """Build the nahw/sarf lesson DOCX from agent-authored lesson JSON.

    data shape (see references/lesson-schema.md in the skill for the full spec):
      {title, subtitle, sections: [{heading, blocks, subsections, section_summary, table, concept_map}]}
      Subsections share the same shape (minus section_summary), so every level
      may carry its own table and concept map.
      Block types: paragraph | evidence (Alfiyya verse block) | bullet_list | numbered_list.

    Concept maps are injected as real Word SmartArt after the initial save.
    If injection fails for a node, a visible failure note (with the
    technical reason) replaces the diagram - never an image fallback.
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    doc = setup_document()
    add_heading(doc, data["title"], level=0)
    if data.get("subtitle"):
        p = doc.add_paragraph()
        set_paragraph_rtl(p, align="center", before=0, after=160)
        add_text_runs(p, data["subtitle"], size=20, color=BROWN, bold=True)

    smartart_jobs: list[tuple[int, dict[str, Any], str]] = []

    for section in data["sections"]:
        _render_node(doc, section, level=1, smartart_jobs=smartart_jobs)

    doc.save(output_path)

    smartart_failures: list[dict[str, str]] = []
    smartart_success = 0
    for idx, tree, section_heading in smartart_jobs:
        try:
            smartart.inject_smartart(output_path, tree, diagram_index=idx)
            smartart_success += 1
        except smartart.SmartArtError as exc:
            logger.warning("SmartArt injection failed for section %r (idx=%s): %s", section_heading, idx, exc)
            note = f"⚠ تَعَذَّرَ تَوْلِيدُ الخَرِيطَةِ المَفَاهِيمِيَّةِ (SmartArt) لِهَذَا المِحْوَرِ. السَّبَبُ التِّقْنِيُّ: {exc}"
            try:
                smartart.replace_placeholder_with_note(output_path, idx, note)
            except smartart.SmartArtError as note_exc:
                logger.error("Failed to insert SmartArt failure note for idx=%s: %s", idx, note_exc)
            smartart_failures.append({"section": section_heading, "reason": str(exc)})

    return BuildReport(
        output_path=output_path,
        section_count=len(data["sections"]),
        smartart_success=smartart_success,
        smartart_failures=smartart_failures,
    )
