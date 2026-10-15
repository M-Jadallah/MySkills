#!/usr/bin/env python3
"""Deterministic TXT -> DOCX formatter for vocalized hadith text.

The transformer is intentionally conservative. It removes only structurally
proven footnote blocks/page furniture, deletes parenthesized numeric footnote
references, and replaces the exact salutation phrase configured by the user.
All other Arabic letters and combining marks are preserved.

Version 1.1.1 retains the 1.1 feature set and fixes font fitting:
- font size is measured against a full empty page, never the leftover space;
- only genuinely overlong hadiths are resized;
- the largest fitting size is selected by renderer-verified binary search;
- page breaks are inserted before otherwise-splitting units instead of shrinking them.

Version 1.1 adds:
- table-free editable Word paragraphs;
- black borders around green book/chapter headings;
- full narrator-chain coloring;
- all quoted matn variants in dark brown;
- bold definition terms before a colon;
- automatic per-hadith font fitting so a hadith never spans pages;
- strict fixed-page part boundaries (except the naturally shorter last part).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import shutil
import subprocess
import tempfile
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Sequence

try:
    import fitz  # PyMuPDF
except Exception:  # pragma: no cover
    fitz = None

from docx import Document
from docx.enum.section import WD_SECTION_START
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK, WD_LINE_SPACING
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor

ARABIC_DIACRITICS_RE = re.compile("[\u0610-\u061a\u064b-\u065f\u0670\u06d6-\u06ed]")
SEPARATOR_RE = re.compile(r"^\s*_{10,}\s*$")
PAGE_FURNITURE_RE = re.compile(r"^\s*.*(?:\(|\[)\s*ص\s*[:：]\s*\d+\s*(?:\)|\])\s*$")
FOOTNOTE_REF_RE = re.compile(r"\(\s*\d+\s*\)")
FOOTNOTE_START_RE = re.compile(r"^\s*\(\s*\d+\s*\)")
HADITH_START_RE = re.compile(r"^\s*(\d+)\s*[-–—]\s+")
RADI_RE = re.compile(r"رضي الله (?:عنهما|عنهم|عنهن|عنه|عنها)")
MARKER_RE = re.compile(r"HFU(\d{6})([SE])")
PART_MARKER_RE = re.compile(r"HFPART(\d{3})")

NARRATION_TRIGGERS = {"عن", "حدثنا", "حدثني", "اخبرنا", "اخبرني"}
NARRATION_BOUNDARIES = {
    "عن", "حدثنا", "حدثني", "اخبرنا", "اخبرني", "قال", "قالت", "قالوا",
    "يقول", "ان", "انه", "انها", "سمعت", "راى", "رأى", "شهدت", "سال",
    "سأل", "رضي", "رسول", "النبي",
}
BACKSCAN_BOUNDARIES = {
    "عن", "قال", "قالت", "قالوا", "يقول", "سمعت", "حدثنا", "حدثني",
    "اخبرنا", "اخبرني", "ان", "انه", "انها", "راى", "رأى", "شهدت",
    "سال", "سأل", "رسول", "النبي", "وفي", "وله", "ولمسلم", "في", "حديث",
}

PART_ORDINALS = {
    1: "الأَوَّلُ", 2: "الثَّانِي", 3: "الثَّالِثُ", 4: "الرَّابِعُ",
    5: "الخَامِسُ", 6: "السَّادِسُ", 7: "السَّابِعُ", 8: "الثَّامِنُ",
    9: "التَّاسِعُ", 10: "العَاشِرُ", 11: "الحَادِي عَشَرَ",
    12: "الثَّانِي عَشَرَ", 13: "الثَّالِثَ عَشَرَ", 14: "الرَّابِعَ عَشَرَ",
    15: "الخَامِسَ عَشَرَ", 16: "السَّادِسَ عَشَرَ", 17: "السَّابِعَ عَشَرَ",
    18: "الثَّامِنَ عَشَرَ", 19: "التَّاسِعَ عَشَرَ", 20: "العِشْرُونَ",
    21: "الحَادِي وَالعِشْرُونَ", 22: "الثَّانِي وَالعِشْرُونَ",
    23: "الثَّالِثُ وَالعِشْرُونَ", 24: "الرَّابِعُ وَالعِشْرُونَ",
    25: "الخَامِسُ وَالعِشْرُونَ", 26: "السَّادِسُ وَالعِشْرُونَ",
    27: "السَّابِعُ وَالعِشْرُونَ", 28: "الثَّامِنُ وَالعِشْرُونَ",
    29: "التَّاسِعُ وَالعِشْرُونَ", 30: "الثَّلَاثُونَ",
}


@dataclass
class Unit:
    index: int
    kind: str  # title | hadith | body
    text: str
    hadith_number: str | None = None
    source_file: str | None = None


@dataclass
class CleanStats:
    page_markers_removed: int = 0
    separators_removed: int = 0
    footnote_blocks_removed: int = 0
    footnote_reference_numbers_removed: int = 0
    salutation_replacements: int = 0
    repair_passes: int = 0


@dataclass
class LayoutResult:
    page_count: int
    boundaries: list[int]
    padding_pages: list[int]
    part_start_pages: list[int]
    unit_pages: dict[int, tuple[int, int]]
    warnings: list[str]
    unit_font_sizes: dict[int, float] = field(default_factory=dict)
    page_break_before_units: list[int] = field(default_factory=list)


def strip_diacritics(text: str) -> str:
    return ARABIC_DIACRITICS_RE.sub("", text)


def normalized_word(text: str) -> str:
    text = strip_diacritics(text)
    text = text.replace("ٱ", "ا").replace("أ", "ا").replace("إ", "ا").replace("آ", "ا")
    return re.sub(r"[^\u0621-\u064a]", "", text)


def read_utf8(path: Path) -> str:
    raw = path.read_bytes()
    if raw.startswith(b"\xef\xbb\xbf"):
        return raw.decode("utf-8-sig")
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError(f"The input TXT must be UTF-8 encoded: {path}") from exc


def _count_separator(line: str, stats: CleanStats) -> bool:
    if SEPARATOR_RE.match(line):
        stats.separators_removed += 1
        return True
    return False


def _process_page_chunk(lines: list[str], stats: CleanStats) -> list[str]:
    """Remove the final structurally proven footnote block in a page chunk."""
    sep_positions = [i for i, line in enumerate(lines) if SEPARATOR_RE.match(line)]
    kept = lines
    if sep_positions:
        last_sep = sep_positions[-1]
        after = lines[last_sep + 1 :]
        first_nonblank = next((x for x in after if x.strip()), "")
        if first_nonblank and FOOTNOTE_START_RE.match(first_nonblank):
            stats.footnote_blocks_removed += 1
            kept = lines[:last_sep]
    return [line for line in kept if not _count_separator(line, stats)]


def is_title(line: str, prefixes: Sequence[str]) -> bool:
    stripped = line.strip()
    if not stripped:
        return False
    plain = strip_diacritics(stripped)
    plain = plain.replace("ٱ", "ا").replace("أ", "ا").replace("إ", "ا").replace("آ", "ا")
    return any(plain.startswith(prefix) for prefix in prefixes)


def is_subentry_line(line: str) -> bool:
    plain = strip_diacritics(line.strip())
    plain = plain.replace("ٱ", "ا").replace("أ", "ا").replace("إ", "ا").replace("آ", "ا")
    return plain.startswith(("وفي", "ولمسلم", "وله", "وللبخاري", "وفي رواية", "وفي لفظ"))


def clean_source(text: str, replacements: dict[str, str]) -> tuple[str, CleanStats]:
    """Clean page footnotes while preserving the body character stream."""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    stats = CleanStats()
    pages: list[list[str]] = []
    current: list[str] = []

    for line in text.split("\n"):
        if PAGE_FURNITURE_RE.match(line) and "ص" in line:
            pages.append(_process_page_chunk(current, stats))
            current = []
            stats.page_markers_removed += 1
        else:
            current.append(line)
    pages.append(_process_page_chunk(current, stats))

    merged_lines: list[str] = []
    for page_idx, page_lines in enumerate(pages):
        while page_lines and not page_lines[0].strip():
            page_lines.pop(0)
        while page_lines and not page_lines[-1].strip():
            page_lines.pop()
        if not page_lines:
            continue
        if merged_lines and page_idx > 0:
            first = page_lines[0]
            prev = merged_lines[-1]
            first_is_new_unit = bool(HADITH_START_RE.match(first)) or is_title(first, ["كتاب", "باب", "فصل"])
            if prev.strip() and not first_is_new_unit and not is_subentry_line(first):
                merged_lines[-1] = prev.rstrip() + " " + first.lstrip()
                page_lines = page_lines[1:]
        merged_lines.extend(page_lines)

    cleaned = "\n".join(merged_lines)
    cleaned, count = FOOTNOTE_REF_RE.subn("", cleaned)
    stats.footnote_reference_numbers_removed = count
    for old, new in replacements.items():
        cleaned, count = re.subn(re.escape(old), lambda _: new, cleaned)
        stats.salutation_replacements += count

    cleaned = re.sub(r"\n[ \t]+\n", "\n\n", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned).strip() + "\n"
    return cleaned, stats


def _join_unit_lines(lines: list[str]) -> str:
    out: list[str] = []
    pending_break = False
    for line in lines:
        if not line.strip():
            pending_break = True
            continue
        piece = line.strip()
        if not out:
            out.append(piece)
        elif pending_break or is_subentry_line(piece) or (":" in piece[:40] and not piece.startswith("«")):
            out.append("\n" + piece)
        else:
            out.append(" " + piece)
        pending_break = False
    return "".join(out).strip()


def parse_units(cleaned: str, title_prefixes: Sequence[str], source_file: str | None = None) -> list[Unit]:
    units: list[Unit] = []
    current_kind: str | None = None
    current_lines: list[str] = []
    current_num: str | None = None

    def flush() -> None:
        nonlocal current_kind, current_lines, current_num
        if current_kind and current_lines:
            text = _join_unit_lines(current_lines)
            if text:
                units.append(Unit(len(units), current_kind, text, current_num, source_file))
        current_kind = None
        current_lines = []
        current_num = None

    for line in cleaned.splitlines():
        if is_title(line, title_prefixes):
            flush()
            units.append(Unit(len(units), "title", line.strip(), None, source_file))
            continue
        match = HADITH_START_RE.match(line)
        if match:
            flush()
            current_kind = "hadith"
            current_num = match.group(1)
            current_lines = [line]
            continue
        if current_kind == "hadith":
            current_lines.append(line)
        elif line.strip():
            if current_kind != "body":
                flush()
                current_kind = "body"
            current_lines.append(line)
        elif current_kind:
            current_lines.append(line)
    flush()
    for i, unit in enumerate(units):
        unit.index = i
    return units


def compact_chars(text: str) -> str:
    return re.sub(r"\s+", "", text)


def audit_unit_preservation(cleaned: str, units: Sequence[Unit]) -> None:
    reconstructed = "\n".join(unit.text for unit in units)
    if compact_chars(cleaned) != compact_chars(reconstructed):
        raise RuntimeError("Preservation audit failed: parsed output changed non-whitespace characters.")


def validate_cleaned(cleaned: str) -> list[str]:
    issues: list[str] = []
    if SEPARATOR_RE.search(cleaned):
        issues.append("separator_remains")
    if PAGE_FURNITURE_RE.search(cleaned):
        issues.append("page_furniture_remains")
    if FOOTNOTE_REF_RE.search(cleaned):
        issues.append("footnote_reference_remains")
    return issues


def process_source_with_repairs(
    original: str,
    config: dict,
    *,
    source_file: str | None = None,
    max_attempts: int = 4,
) -> tuple[str, CleanStats, list[Unit], list[dict]]:
    """Retry safe structural processing before declaring a source irreparable.

    Repairs never invent, rewrite, or normalize hadith text. They only rerun
    structural cleaning on residual page furniture and rebuild lossless units.
    """
    attempt_input = original
    repair_log: list[dict] = []
    aggregate = CleanStats()
    last_error: Exception | None = None

    for attempt in range(1, max_attempts + 1):
        try:
            cleaned, stats = clean_source(attempt_input, config["replace_exact"] if attempt == 1 else {})
            aggregate.page_markers_removed += stats.page_markers_removed
            aggregate.separators_removed += stats.separators_removed
            aggregate.footnote_blocks_removed += stats.footnote_blocks_removed
            aggregate.footnote_reference_numbers_removed += stats.footnote_reference_numbers_removed
            aggregate.salutation_replacements += stats.salutation_replacements
            units = parse_units(cleaned, config["title_prefixes_unvocalized"], source_file)
            if not units:
                raise RuntimeError("No content units were detected.")
            audit_unit_preservation(cleaned, units)
            issues = validate_cleaned(cleaned)
            repair_log.append({"attempt": attempt, "issues": issues, "status": "PASS" if not issues else "RETRY"})
            if not issues:
                aggregate.repair_passes = attempt - 1
                return cleaned, aggregate, units, repair_log
            attempt_input = cleaned
        except Exception as exc:  # retry from the latest safe character stream
            last_error = exc
            repair_log.append({"attempt": attempt, "status": "RETRY", "error": str(exc)})
            attempt_input = attempt_input.replace("\r\n", "\n").replace("\r", "\n")

    detail = json.dumps(repair_log, ensure_ascii=False)
    raise RuntimeError(f"Automatic text-safety repair exhausted {max_attempts} attempts: {last_error}; log={detail}")


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def set_paragraph_bidi(paragraph) -> None:
    ppr = paragraph._p.get_or_add_pPr()
    if ppr.find(qn("w:bidi")) is None:
        ppr.append(OxmlElement("w:bidi"))


def set_paragraph_keep_together(paragraph, keep_with_next: bool = False) -> None:
    paragraph.paragraph_format.keep_together = True
    paragraph.paragraph_format.keep_with_next = keep_with_next
    paragraph.paragraph_format.widow_control = False
    ppr = paragraph._p.get_or_add_pPr()
    if ppr.find(qn("w:keepLines")) is None:
        ppr.append(OxmlElement("w:keepLines"))
    if keep_with_next and ppr.find(qn("w:keepNext")) is None:
        ppr.append(OxmlElement("w:keepNext"))


def set_run_style(run, *, font: str, size_pt: float, color: str, bold: bool = False, rtl: bool = True) -> None:
    run.font.name = font
    run.font.size = Pt(size_pt)
    run.font.bold = bold
    run.font.color.rgb = RGBColor.from_string(color)
    rpr = run._r.get_or_add_rPr()
    rfonts = rpr.find(qn("w:rFonts"))
    if rfonts is None:
        rfonts = OxmlElement("w:rFonts")
        rpr.insert(0, rfonts)
    for attr in ("ascii", "hAnsi", "eastAsia", "cs"):
        rfonts.set(qn(f"w:{attr}"), font)
    for tag in ("w:sz", "w:szCs"):
        element = rpr.find(qn(tag))
        if element is None:
            element = OxmlElement(tag)
            rpr.append(element)
        element.set(qn("w:val"), str(int(round(size_pt * 2))))
    if rtl and rpr.find(qn("w:rtl")) is None:
        rpr.append(OxmlElement("w:rtl"))


def add_debug_marker(paragraph, marker: str) -> None:
    run = paragraph.add_run(marker)
    set_run_style(run, font="Arial", size_pt=1, color="FFFFFF", rtl=False)


def _token_spans(text: str) -> list[tuple[int, int, str]]:
    return [(m.start(), m.end(), m.group()) for m in re.finditer(r"[\u0600-\u06FF]+|[^\u0600-\u06FF\s]+", text)]


def _merge_spans(spans: Sequence[tuple[int, int]]) -> list[tuple[int, int]]:
    if not spans:
        return []
    ordered = sorted(spans)
    merged = [list(ordered[0])]
    for start, end in ordered[1:]:
        if start <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], end)
        else:
            merged.append([start, end])
    return [(a, b) for a, b in merged]


def narrator_chain_spans(text: str) -> list[tuple[int, int]]:
    """Color every narrator identity in the chain, not only one companion."""
    spans: list[tuple[int, int]] = []
    tokens = _token_spans(text)

    # Forward scan after narration triggers (عن، حدثنا، أخبرنا...).
    for pos, (start, end, token) in enumerate(tokens):
        if normalized_word(token) not in NARRATION_TRIGGERS:
            continue
        capture_start: int | None = None
        capture_end: int | None = None
        for next_start, next_end, next_token in tokens[pos + 1 :]:
            normalized = normalized_word(next_token)
            if next_token in {":", ".", "؛", ";", "«", "»"} or normalized in NARRATION_BOUNDARIES:
                break
            if next_token.strip() in {"،", ",", "-", "–", "—"}:
                if capture_start is not None:
                    capture_end = next_end
                continue
            if capture_start is None:
                capture_start = next_start
            capture_end = next_end
        if capture_start is not None and capture_end is not None:
            while capture_end > capture_start and text[capture_end - 1] in " \t\n،,:;-–—":
                capture_end -= 1
            spans.append((capture_start, capture_end))

    # Backward scan before رضي الله... catches names in later attached narrations.
    for radi in RADI_RE.finditer(text):
        before = [t for t in tokens if t[1] <= radi.start()]
        if not before:
            continue
        scan_start = before[-1][0]
        for start, end, token in reversed(before[-32:]):
            normalized = normalized_word(token)
            if token in {":", ".", "؛", ";", "«", "»"} or normalized in BACKSCAN_BOUNDARIES:
                scan_start = end
                break
            scan_start = start
        while scan_start < radi.start() and text[scan_start] in " \t\n،,:;-–—":
            scan_start += 1
        if scan_start < radi.start():
            spans.append((scan_start, radi.start()))
    return _merge_spans(spans)


def matn_spans(text: str) -> list[tuple[int, int]]:
    spans: list[tuple[int, int]] = []
    stack: list[int] = []
    for i, char in enumerate(text):
        if char == "«":
            stack.append(i)
        elif char == "»" and stack:
            start = stack.pop()
            if not stack:
                spans.append((start, i + 1))
    return spans


def meaning_term_spans(text: str) -> list[tuple[int, int]]:
    """Bold a definition term (including its colon) on a separate line."""
    spans: list[tuple[int, int]] = []
    offset = 0
    for line in text.splitlines(keepends=True):
        stripped = line.lstrip()
        leading = len(line) - len(stripped)
        colon = stripped.find(":")
        if 0 < colon <= 60:
            prefix_plain = normalized_word(stripped[:colon])
            starts_as_hadith = bool(HADITH_START_RE.match(stripped))
            starts_as_variant = is_subentry_line(stripped)
            narration_like = prefix_plain in {"قال", "قالت", "قالوا", "عن", "حدثنا", "اخبرنا"}
            if not starts_as_hadith and not starts_as_variant and not narration_like and "«" not in stripped[:colon]:
                spans.append((offset + leading, offset + leading + colon + 1))
        offset += len(line)
    return spans


def style_segments(text: str) -> list[tuple[str, str, bool]]:
    """Return (text, role, bold) segments with deterministic precedence."""
    number_match = re.match(r"^\s*\d+\s*[-–—]", text)
    number = (number_match.start(), number_match.end()) if number_match else None
    narrators = narrator_chain_spans(text)
    matn = matn_spans(text)
    meanings = meaning_term_spans(text)
    bounds = {0, len(text)}
    if number:
        bounds.update(number)
    for start, end in narrators + matn + meanings:
        bounds.add(start)
        bounds.add(end)
    ordered = sorted(bounds)
    result: list[tuple[str, str, bool]] = []
    for a, b in zip(ordered, ordered[1:]):
        if a == b:
            continue
        role = "isnad"
        bold = False
        if any(a >= start and b <= end for start, end in matn):
            role, bold = "matn", True
        elif number and a >= number[0] and b <= number[1]:
            role, bold = "number", True
        elif any(a >= start and b <= end for start, end in narrators):
            role = "narrator"
        elif any(a >= start and b <= end for start, end in meanings):
            role, bold = "isnad", True
        chunk = text[a:b]
        if result and result[-1][1:] == (role, bold):
            result[-1] = (result[-1][0] + chunk, role, bold)
        else:
            result.append((chunk, role, bold))
    return result


def add_page_field(paragraph, config: dict) -> None:
    paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    set_paragraph_bidi(paragraph)
    for kind, text in (("begin", None), (None, "PAGE"), ("separate", None), (None, "1"), ("end", None)):
        run = paragraph.add_run()
        set_run_style(run, font=config["font_name"], size_pt=config["footer_font_size_pt"], color="000000")
        if kind:
            fld = OxmlElement("w:fldChar")
            fld.set(qn("w:fldCharType"), kind)
            run._r.append(fld)
        elif text == "PAGE":
            instr = OxmlElement("w:instrText")
            instr.set(qn("xml:space"), "preserve")
            instr.text = " PAGE "
            run._r.append(instr)
        else:
            node = OxmlElement("w:t")
            node.text = text
            run._r.append(node)


def configure_section(section, config: dict, part_number: int, debug_markers: bool, first: bool) -> None:
    page = config["page"]
    section.page_width = Inches(page["width_inches"])
    section.page_height = Inches(page["height_inches"])
    section.top_margin = Inches(page["top_margin_inches"])
    section.bottom_margin = Inches(page["bottom_margin_inches"])
    section.left_margin = Inches(page["left_margin_inches"])
    section.right_margin = Inches(page["right_margin_inches"])
    section.header_distance = Inches(page["header_distance_inches"])
    section.footer_distance = Inches(page["footer_distance_inches"])

    header = section.header
    header.is_linked_to_previous = False
    for para in list(header.paragraphs):
        para._element.getparent().remove(para._element)
    blank = header.add_paragraph()
    blank.alignment = WD_ALIGN_PARAGRAPH.CENTER
    set_paragraph_bidi(blank)
    title = header.add_paragraph()
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    set_paragraph_bidi(title)
    run = title.add_run(f"الجُزْءُ {PART_ORDINALS.get(part_number, str(part_number))}")
    set_run_style(run, font=config["font_name"], size_pt=config["header_font_size_pt"], color=config["colors"]["part_header"], bold=True)
    if debug_markers:
        add_debug_marker(title, f"HFPART{part_number:03d}")

    footer = section.footer
    if not first:
        footer.is_linked_to_previous = True
    else:
        footer.is_linked_to_previous = False
        for para in list(footer.paragraphs):
            para._element.getparent().remove(para._element)
        add_page_field(footer.add_paragraph(), config)


def apply_document_settings(doc: Document, config: dict) -> None:
    settings = doc.settings._element
    zoom = settings.find(qn("w:zoom"))
    if zoom is not None and zoom.get(qn("w:percent")) is None:
        zoom.set(qn("w:percent"), "100")
    update = settings.find(qn("w:updateFields"))
    if update is None:
        update = OxmlElement("w:updateFields")
        compat = settings.find(qn("w:compat"))
        settings.insert(settings.index(compat) if compat is not None else len(settings), update)
    update.set(qn("w:val"), "true")
    theme_lang = settings.find(qn("w:themeFontLang"))
    if theme_lang is None:
        theme_lang = OxmlElement("w:themeFontLang")
        settings.append(theme_lang)
    theme_lang.set(qn("w:bidi"), "ar-SA")


def set_paragraph_box(paragraph, *, fill: str, border_color: str, border_size: int = 12, padding: int = 4) -> None:
    ppr = paragraph._p.get_or_add_pPr()
    shd = ppr.find(qn("w:shd"))
    if shd is None:
        shd = OxmlElement("w:shd")
        ppr.insert(0, shd)
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), fill)

    borders = ppr.find(qn("w:pBdr"))
    if borders is None:
        borders = OxmlElement("w:pBdr")
        ppr.append(borders)
    for edge in ("top", "left", "bottom", "right"):
        element = borders.find(qn(f"w:{edge}"))
        if element is None:
            element = OxmlElement(f"w:{edge}")
            borders.append(element)
        element.set(qn("w:val"), "single")
        element.set(qn("w:sz"), str(border_size))
        element.set(qn("w:space"), str(padding))
        element.set(qn("w:color"), border_color)


def normalize_paragraph_property_order(doc: Document) -> None:
    """Keep generated paragraph properties in the OOXML schema order."""
    tags = (
        "pStyle", "keepNext", "keepLines", "pageBreakBefore", "framePr", "widowControl",
        "numPr", "suppressLineNumbers", "pBdr", "shd", "tabs", "suppressAutoHyphens",
        "kinsoku", "wordWrap", "overflowPunct", "topLinePunct", "autoSpaceDE",
        "autoSpaceDN", "bidi", "adjustRightInd", "snapToGrid", "spacing", "ind",
        "contextualSpacing", "mirrorIndents", "suppressOverlap", "jc", "textDirection",
        "textAlignment", "textboxTightWrap", "outlineLvl", "divId", "cnfStyle", "rPr",
        "sectPr", "pPrChange",
    )
    order = {qn(f"w:{tag}"): position for position, tag in enumerate(tags)}
    roots = [doc._element]
    for section in doc.sections:
        roots.extend((section.header._element, section.footer._element))
    for root in roots:
        for ppr in root.iter(qn("w:pPr")):
            children = list(ppr)
            children.sort(key=lambda child: order.get(child.tag, len(order)))
            ppr[:] = children


def add_title(doc: Document, unit: Unit, config: dict, debug_markers: bool) -> None:
    paragraph = doc.add_paragraph()
    paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    set_paragraph_bidi(paragraph)
    set_paragraph_keep_together(paragraph, keep_with_next=True)
    paragraph.paragraph_format.space_before = Pt(15)
    paragraph.paragraph_format.space_after = Pt(15)
    set_paragraph_box(
        paragraph,
        fill=config["colors"]["title_fill"],
        border_color=config["colors"].get("title_border", "000000"),
        border_size=int(config.get("title_border_size_eighth_points", 12)),
    )
    if debug_markers:
        add_debug_marker(paragraph, f"HFU{unit.index:06d}S")
    run = paragraph.add_run(unit.text)
    set_run_style(run, font=config["font_name"], size_pt=config["title_font_size_pt"], color=config["colors"]["title_text"], bold=True)
    if debug_markers:
        add_debug_marker(paragraph, f"HFU{unit.index:06d}E")


def add_text_unit(
    doc: Document, unit: Unit, config: dict, debug_markers: bool, font_size: float,
    *, page_break_before: bool = False,
) -> None:
    """Add a fully editable, table-free paragraph unit."""
    paragraph = doc.add_paragraph()
    paragraph.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    set_paragraph_bidi(paragraph)
    set_paragraph_keep_together(paragraph)
    paragraph.paragraph_format.line_spacing_rule = WD_LINE_SPACING.ONE_POINT_FIVE
    paragraph.paragraph_format.line_spacing = config["line_spacing"]
    paragraph.paragraph_format.space_after = Pt(config["paragraph_space_after_pt"])
    paragraph.paragraph_format.page_break_before = page_break_before
    if debug_markers:
        add_debug_marker(paragraph, f"HFU{unit.index:06d}S")
    if unit.kind == "hadith":
        for chunk, role, bold in style_segments(unit.text):
            run = paragraph.add_run(chunk)
            set_run_style(run, font=config["font_name"], size_pt=font_size, color=config["colors"][role], bold=bold)
    else:
        # Body text may contain a definition term; use the same segmenter.
        for chunk, role, bold in style_segments(unit.text):
            run = paragraph.add_run(chunk)
            color_role = role if role in config["colors"] else "isnad"
            set_run_style(run, font=config["font_name"], size_pt=font_size, color=config["colors"][color_role], bold=bold)
    if debug_markers:
        add_debug_marker(paragraph, f"HFU{unit.index:06d}E")


def build_document(
    units: Sequence[Unit],
    config: dict,
    output: Path,
    boundaries: Sequence[int] | None = None,
    padding_pages: Sequence[int] | None = None,
    debug_markers: bool = False,
    unit_font_sizes: dict[int, float] | None = None,
    page_break_before_units: Sequence[int] | None = None,
) -> None:
    boundaries = list(boundaries or [])
    padding_pages = list(padding_pages or [0] * len(boundaries))
    if len(padding_pages) != len(boundaries):
        raise ValueError("padding_pages must match boundaries")
    boundary_map = {idx: pos for pos, idx in enumerate(boundaries)}
    unit_font_sizes = unit_font_sizes or {}
    page_break_before_set = set(page_break_before_units or [])

    doc = Document()
    body = doc._element.body
    for child in list(body):
        if child.tag == qn("w:p"):
            body.remove(child)
    apply_document_settings(doc, config)
    configure_section(doc.sections[0], config, 1, debug_markers, first=True)

    part_num = 1
    for unit in units:
        if unit.index in boundary_map:
            boundary_position = boundary_map[unit.index]
            for _ in range(padding_pages[boundary_position]):
                doc.add_paragraph().add_run().add_break(WD_BREAK.PAGE)
            part_num += 1
            section = doc.add_section(WD_SECTION_START.NEW_PAGE)
            configure_section(section, config, part_num, debug_markers, first=False)
        if unit.kind == "title":
            add_title(doc, unit, config, debug_markers)
        else:
            font_size = unit_font_sizes.get(unit.index, float(config["body_font_size_pt"]))
            add_text_unit(
                doc, unit, config, debug_markers, font_size,
                page_break_before=(
                    unit.index in page_break_before_set
                    and unit.index not in boundary_map
                    and unit.index != units[0].index
                ),
            )

    normalize_paragraph_property_order(doc)
    output.parent.mkdir(parents=True, exist_ok=True)
    doc.save(output)


def find_soffice() -> str | None:
    for candidate in ("libreoffice", "soffice"):
        path = shutil.which(candidate)
        if path:
            return path
    if os.name == "nt":
        for candidate in (
            Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "LibreOffice" / "program" / "soffice.exe",
            Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")) / "LibreOffice" / "program" / "soffice.exe",
        ):
            if candidate.is_file():
                return str(candidate)
    return None


def render_pdf(docx_path: Path, workdir: Path) -> Path:
    """Render DOCX with isolated LibreOffice profiles and one safe retry."""
    soffice = find_soffice()
    if not soffice:
        raise RuntimeError("LibreOffice/soffice is required for exact pagination and font fitting.")
    docx_path = docx_path.resolve()
    workdir = workdir.resolve()
    outdir = workdir / "pdf"
    outdir.mkdir(parents=True, exist_ok=True)

    failures: list[str] = []
    for attempt in range(2):
        profile = workdir / f"lo_profile_{attempt}"
        home = workdir / f"home_{attempt}"
        if profile.exists():
            shutil.rmtree(profile, ignore_errors=True)
        profile.mkdir(parents=True, exist_ok=True)
        home.mkdir(parents=True, exist_ok=True)
        env = os.environ.copy()
        env["HOME"] = str(home)
        command = [
            soffice,
            "--headless",
            "--invisible",
            "--norestore",
            "--nolockcheck",
            f"-env:UserInstallation={profile.as_uri()}",
            "--convert-to",
            "pdf",
            "--outdir",
            str(outdir),
            str(docx_path),
        ]
        try:
            proc = subprocess.run(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                env=env,
                timeout=150,
            )
        except subprocess.TimeoutExpired as exc:
            failures.append(f"attempt {attempt + 1}: timeout after {exc.timeout}s")
            continue
        pdf = outdir / f"{docx_path.stem}.pdf"
        if proc.returncode == 0 and pdf.exists() and pdf.stat().st_size > 0:
            return pdf
        failures.append(f"attempt {attempt + 1}: {proc.stdout}\n{proc.stderr}")
    raise RuntimeError("LibreOffice PDF conversion failed after retry: " + " | ".join(failures))

def extract_pdf_markers(pdf_path: Path) -> tuple[int, dict[int, tuple[int, int]], list[int]]:
    if fitz is None:
        raise RuntimeError("PyMuPDF is required for pagination analysis.")
    pdf = fitz.open(pdf_path)
    starts: dict[int, int] = {}
    ends: dict[int, int] = {}
    part_starts: dict[int, int] = {}
    for page_index, page in enumerate(pdf, start=1):
        compact = re.sub(r"\s+", "", page.get_text("text"))
        for match in MARKER_RE.finditer(compact):
            index = int(match.group(1))
            if match.group(2) == "S":
                starts.setdefault(index, page_index)
            else:
                ends[index] = page_index
        for match in PART_MARKER_RE.finditer(compact):
            part_starts.setdefault(int(match.group(1)), page_index)
    unit_pages = {index: (starts[index], ends.get(index, starts[index])) for index in starts}
    ordered_part_starts = [part_starts[key] for key in sorted(part_starts)]
    return len(pdf), unit_pages, ordered_part_starts


def _render_units_for_markers(
    units: Sequence[Unit],
    config: dict,
    workdir: Path,
    name: str,
    *,
    boundaries: Sequence[int] | None = None,
    padding_pages: Sequence[int] | None = None,
    unit_font_sizes: dict[int, float] | None = None,
    page_break_before_units: Sequence[int] | None = None,
) -> tuple[int, dict[int, tuple[int, int]], list[int]]:
    docx = workdir / f"{name}.docx"
    build_document(
        units, config, docx, boundaries, padding_pages,
        debug_markers=True, unit_font_sizes=unit_font_sizes,
        page_break_before_units=page_break_before_units,
    )
    pdf = render_pdf(docx, workdir / f"{name}_render")
    return extract_pdf_markers(pdf)


def _isolated_unit_fits(unit: Unit, size: float, config: dict, workdir: Path, sequence: int) -> bool:
    isolated = Unit(unit.index, unit.kind, unit.text, unit.hadith_number, unit.source_file)
    page_count, pages, _ = _render_units_for_markers(
        [isolated], config, workdir, f"fit_{unit.index:06d}_{sequence:02d}_{int(size * 2):03d}",
        unit_font_sizes={unit.index: size},
    )
    span = pages.get(unit.index)
    return bool(span and span[0] == span[1] and page_count == 1)


def _batch_candidate_fits(
    unit: Unit,
    candidate_sizes: Sequence[float],
    config: dict,
    workdir: Path,
    label: str,
) -> dict[float, bool]:
    """Measure several font candidates in one LibreOffice render."""
    sizes = list(dict.fromkeys(round(float(size), 4) for size in candidate_sizes))
    if not sizes:
        return {}
    if len(sizes) > 200:
        raise ValueError("Too many font-fit candidates in one batch")
    variants: list[Unit] = []
    size_map: dict[int, float] = {}
    # Reserved marker range; the generated document exists only for measurement.
    for position, size in enumerate(sizes):
        index = 700000 + position
        variants.append(Unit(index, unit.kind, unit.text, unit.hadith_number, unit.source_file))
        size_map[index] = size
    forced = [variant.index for variant in variants[1:]]
    _, pages, _ = _render_units_for_markers(
        variants,
        config,
        workdir,
        label,
        unit_font_sizes=size_map,
        page_break_before_units=forced,
    )
    return {
        size_map[variant.index]: (
            variant.index in pages and pages[variant.index][0] == pages[variant.index][1]
        )
        for variant in variants
    }


def find_largest_fitting_font(unit: Unit, config: dict, workdir: Path) -> float:
    """Find the maximum fitting size with two renderer batches.

    The default size is known to overflow. A coarse descending batch finds a
    narrow fitting/failing bracket near the default; a second batch tests every
    configured precision step inside that bracket. This gives the exact largest
    fitting size without launching LibreOffice once per candidate.
    """
    base = float(config["body_font_size_pt"])
    minimum = float(config.get("minimum_fitted_font_size_pt", 1.0))
    step = float(config.get("font_fit_step_pt", 0.25))
    if step <= 0:
        raise ValueError("font_fit_step_pt must be positive")

    def qfloor(value: float) -> float:
        return round(math.floor((value + 1e-9) / step) * step, 4)

    drops = [1.0, 2.0, 4.0, 8.0, 12.0, 16.0, base - minimum]
    coarse = sorted(
        {qfloor(max(minimum, base - drop)) for drop in drops if base - drop < base},
        reverse=True,
    )
    if qfloor(minimum) not in coarse:
        coarse.append(qfloor(minimum))
    coarse_results = _batch_candidate_fits(unit, coarse, config, workdir, "coarse_candidates")
    fitting = sorted((size for size, fits in coarse_results.items() if fits), reverse=True)
    if not fitting:
        raise RuntimeError(
            f"Hadith unit {unit.hadith_number or unit.index} cannot fit on one page even at {minimum} pt."
        )
    fit_low = fitting[0]
    higher_failures = sorted(size for size, fits in coarse_results.items() if not fits and size > fit_low)
    fail_high = higher_failures[0] if higher_failures else base

    first_tick = int(round(fit_low / step)) + 1
    last_tick = int(math.ceil(fail_high / step)) - 1
    fine = [round(tick * step, 4) for tick in range(first_tick, last_tick + 1)]
    if fine:
        fine_results = _batch_candidate_fits(unit, fine, config, workdir, "fine_candidates")
        fine_fitting = [size for size, fits in fine_results.items() if fits]
        if fine_fitting:
            fit_low = max(fit_low, max(fine_fitting))
    return round(fit_low, 2)

def resolve_unit_font_sizes(units: Sequence[Unit], config: dict, workdir: Path) -> dict[int, float]:
    """Choose the largest readable size that fits each hadith on a full page.

    Crucially, fitting is independent of the unit's position in the combined
    document. A hadith is never shrunk merely to occupy the leftover space at
    the end of a page. Units that fit a fresh page at the default size retain
    the default size; only units that overflow a fresh page are binary-searched
    to the largest renderer-verified fitting size.
    """
    base = float(config["body_font_size_pt"])
    sizes = {unit.index: base for unit in units if unit.kind != "title"}
    hadiths = [unit for unit in units if unit.kind == "hadith"]
    if not hadiths:
        return sizes

    # One catalog render measures every hadith on its own fresh page.
    forced = [unit.index for unit in hadiths[1:]]
    _, pages, _ = _render_units_for_markers(
        hadiths,
        config,
        workdir,
        "isolated_base_catalog",
        unit_font_sizes=sizes,
        page_break_before_units=forced,
    )
    missing = sorted(unit.index for unit in hadiths if unit.index not in pages)
    if missing:
        raise RuntimeError(f"Pagination markers missing during isolated font fitting: {missing}")

    oversized = [unit for unit in hadiths if pages[unit.index][0] != pages[unit.index][1]]
    for unit in oversized:
        sizes[unit.index] = find_largest_fitting_font(unit, config, workdir / f"unit_{unit.index:06d}")

    # Final isolated verification: every hadith must now fit one fresh page.
    _, verified, _ = _render_units_for_markers(
        hadiths,
        config,
        workdir,
        "isolated_final_catalog",
        unit_font_sizes=sizes,
        page_break_before_units=forced,
    )
    split = [unit.index for unit in hadiths if verified.get(unit.index, (0, 1))[0] != verified.get(unit.index, (0, 1))[1]]
    if split:
        raise RuntimeError(f"Isolated font fitting failed for hadith units: {split}")
    return sizes


def resolve_page_breaks_for_hadiths(
    units: Sequence[Unit],
    config: dict,
    workdir: Path,
    unit_font_sizes: dict[int, float],
) -> list[int]:
    """Force a fresh page for fit-capable hadiths that split only by position.

    A split in the combined flow is a pagination-placement issue, not a reason
    to reduce the font. The unit is moved intact to a fresh page and rechecked.
    """
    forced: set[int] = set()
    for iteration in range(6):
        _, pages, _ = _render_units_for_markers(
            units,
            config,
            workdir,
            f"flow_verify_{iteration:02d}",
            unit_font_sizes=unit_font_sizes,
            page_break_before_units=sorted(forced),
        )
        split = [
            unit for unit in units
            if unit.kind == "hadith" and pages.get(unit.index, (0, 1))[0] != pages.get(unit.index, (0, 1))[1]
        ]
        if not split:
            return sorted(forced)
        before = len(forced)
        forced.update(unit.index for unit in split)
        if len(forced) == before:
            raise RuntimeError(
                "Hadith units still split after being forced to fresh pages: "
                + str([unit.index for unit in split])
            )
    raise RuntimeError("Could not stabilize page-break placement for hadith units.")

def choose_initial_boundaries(unit_pages: dict[int, tuple[int, int]], page_count: int, part_pages: int, unit_count: int) -> list[int]:
    boundaries: list[int] = []
    for desired in range(part_pages + 1, page_count + 1, part_pages):
        candidate = next((index for index in range(unit_count) if index in unit_pages and unit_pages[index][0] >= desired), None)
        if candidate is None:
            break
        if candidate > 0 and candidate not in boundaries:
            boundaries.append(candidate)
    return boundaries


def _expected_part_starts(page_count: int, part_pages: int) -> list[int]:
    return list(range(1, page_count + 1, part_pages))


def resolve_layout(
    units: Sequence[Unit],
    config: dict,
    workdir: Path,
    unit_font_sizes: dict[int, float] | None = None,
    page_break_before_units: Sequence[int] | None = None,
) -> LayoutResult:
    part_pages = int(config["part_pages"])
    unit_font_sizes = unit_font_sizes or resolve_unit_font_sizes(units, config, workdir / "font_fit")
    page_break_before_units = list(
        page_break_before_units
        if page_break_before_units is not None
        else resolve_page_breaks_for_hadiths(units, config, workdir / "flow_breaks", unit_font_sizes)
    )
    page_count, unit_pages, _ = _render_units_for_markers(
        units, config, workdir, "provisional", unit_font_sizes=unit_font_sizes,
        page_break_before_units=page_break_before_units,
    )
    if len(unit_pages) != len(units):
        missing = sorted(set(range(len(units))) - set(unit_pages))
        raise RuntimeError(f"Pagination markers missing for units: {missing}")
    split = [unit.index for unit in units if unit.kind == "hadith" and unit_pages[unit.index][0] != unit_pages[unit.index][1]]
    if split:
        raise RuntimeError(f"Hadith units still span pages after font fitting: {split}")

    boundaries = choose_initial_boundaries(unit_pages, page_count, part_pages, len(units))
    padding = [0] * len(boundaries)
    warnings: list[str] = []

    for iteration in range(80):
        page_count, current_pages, part_starts = _render_units_for_markers(
            units, config, workdir, f"layout_{iteration:02d}",
            boundaries=boundaries, padding_pages=padding, unit_font_sizes=unit_font_sizes,
            page_break_before_units=page_break_before_units,
        )
        expected = _expected_part_starts(page_count, part_pages)

        # Add or remove boundaries to match the actual number of parts.
        if len(boundaries) + 1 < len(expected):
            desired = expected[len(boundaries) + 1]
            candidate = next(
                (index for index in range(len(units)) if index in current_pages and current_pages[index][0] >= desired),
                None,
            )
            if candidate is None:
                candidate = len(units) - 1
            if boundaries and candidate <= boundaries[-1]:
                candidate = boundaries[-1] + 1
            if candidate >= len(units):
                raise RuntimeError("Unable to add a required part boundary without losing content.")
            boundaries.append(candidate)
            padding.append(0)
            continue
        if len(boundaries) + 1 > len(expected):
            boundaries.pop()
            padding.pop()
            continue

        changed = False
        for boundary_position, desired in enumerate(expected[1:]):
            actual = part_starts[boundary_position + 1] if len(part_starts) > boundary_position + 1 else None
            if actual is None:
                raise RuntimeError(f"Missing section marker for part {boundary_position + 2}")
            if actual == desired:
                continue
            previous_limit = boundaries[boundary_position - 1] + 1 if boundary_position > 0 else 1
            next_limit = boundaries[boundary_position + 1] - 1 if boundary_position + 1 < len(boundaries) else len(units) - 1
            if actual < desired:
                if boundaries[boundary_position] < next_limit:
                    boundaries[boundary_position] += 1
                else:
                    padding[boundary_position] += desired - actual
                changed = True
                break
            if actual > desired:
                if padding[boundary_position] > 0:
                    padding[boundary_position] = max(0, padding[boundary_position] - (actual - desired))
                elif boundaries[boundary_position] > previous_limit:
                    boundaries[boundary_position] -= 1
                else:
                    raise RuntimeError(
                        f"Cannot force part {boundary_position + 2} to page {desired}; current start is {actual}."
                    )
                changed = True
                break
        if changed:
            continue

        if part_starts != expected:
            raise RuntimeError(f"Strict part-boundary validation failed: expected {expected}, got {part_starts}")
        if page_count > len(expected) * part_pages:
            raise RuntimeError("The final part exceeded the configured page count.")
        split_final = [unit.index for unit in units if unit.kind == "hadith" and current_pages[unit.index][0] != current_pages[unit.index][1]]
        if split_final:
            raise RuntimeError(f"Final layout split hadith units: {split_final}")
        return LayoutResult(
            page_count, boundaries, padding, part_starts, current_pages, warnings,
            unit_font_sizes, list(page_break_before_units),
        )
    raise RuntimeError("Could not stabilize strict part boundaries after 80 iterations.")


def write_clean_text(units: Sequence[Unit], path: Path) -> None:
    path.write_text("\n\n".join(unit.text for unit in units).strip() + "\n", encoding="utf-8")


def format_units(
    units: Sequence[Unit],
    config: dict,
    output_docx: Path,
    workdir: Path,
    *,
    skip_pagination: bool = False,
) -> LayoutResult:
    for index, unit in enumerate(units):
        unit.index = index
    if skip_pagination:
        sizes = {unit.index: float(config["body_font_size_pt"]) for unit in units if unit.kind != "title"}
        layout = LayoutResult(0, [], [], [1], {}, ["Pagination was skipped by request."], sizes, [])
        build_document(units, config, output_docx, unit_font_sizes=sizes)
        return layout
    sizes = resolve_unit_font_sizes(units, config, workdir / "font_fit")
    page_breaks = resolve_page_breaks_for_hadiths(units, config, workdir / "flow_breaks", sizes)
    layout = resolve_layout(units, config, workdir / "layout", sizes, page_breaks)
    build_document(
        units, config, output_docx,
        layout.boundaries, layout.padding_pages,
        debug_markers=False, unit_font_sizes=sizes,
        page_break_before_units=layout.page_break_before_units,
    )
    final_pdf = render_pdf(output_docx, workdir / "final_render")
    final_count = len(fitz.open(final_pdf)) if fitz is not None else layout.page_count
    if final_count != layout.page_count:
        raise RuntimeError(f"Final render page count drifted: expected {layout.page_count}, got {final_count}")
    return layout


def build_audit(
    *,
    config: dict,
    input_path: Path,
    output_docx: Path,
    clean_path: Path,
    original: str,
    cleaned: str,
    units: Sequence[Unit],
    stats: CleanStats,
    repair_log: list[dict],
    layout: LayoutResult,
) -> dict:
    return {
        "skill": config["skill_name"],
        "version": config["version"],
        "input": str(input_path),
        "output": str(output_docx),
        "clean_text": str(clean_path),
        "input_sha256": sha256_text(original),
        "cleaned_non_whitespace_sha256": sha256_text(compact_chars(cleaned)),
        "output_units_non_whitespace_sha256": sha256_text(compact_chars("\n".join(unit.text for unit in units))),
        "preservation_check": "PASS",
        "repair_log": repair_log,
        "stats": asdict(stats),
        "units": {
            "total": len(units),
            "titles": sum(unit.kind == "title" for unit in units),
            "hadiths": sum(unit.kind == "hadith" for unit in units),
            "body_blocks": sum(unit.kind == "body" for unit in units),
            "hadith_numbers": [unit.hadith_number for unit in units if unit.kind == "hadith"],
        },
        "layout": asdict(layout),
        "rules": {
            "font": config["font_name"],
            "default_font_size_pt": config["body_font_size_pt"],
            "font_fitting_enabled": True,
            "hadiths_must_fit_one_page": True,
            "table_free": True,
            "part_pages": config["part_pages"],
            "last_part_may_be_shorter": True,
            "salutation_replacement_only": config["replace_exact"],
            "companion_supplications_preserved": True,
        },
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Format vocalized hadith TXT as a table-free reference-matched Word document.")
    parser.add_argument("input_txt", type=Path)
    parser.add_argument("output_docx", type=Path)
    parser.add_argument("--config", type=Path, default=Path(__file__).resolve().parents[1] / "config" / "default.json")
    parser.add_argument("--audit-json", type=Path)
    parser.add_argument("--clean-txt", type=Path)
    parser.add_argument("--workdir", type=Path)
    parser.add_argument("--max-repair-attempts", type=int, default=4)
    parser.add_argument("--skip-pagination", action="store_true")
    args = parser.parse_args(argv)

    config = json.loads(args.config.read_text(encoding="utf-8"))
    original = read_utf8(args.input_txt)
    cleaned, stats, units, repair_log = process_source_with_repairs(
        original, config, source_file=args.input_txt.name, max_attempts=args.max_repair_attempts,
    )

    temporary = None
    if args.workdir:
        args.workdir.mkdir(parents=True, exist_ok=True)
        workdir = args.workdir
    else:
        temporary = tempfile.TemporaryDirectory(prefix="hadith_formatter_")
        workdir = Path(temporary.name)

    layout = format_units(units, config, args.output_docx, workdir, skip_pagination=args.skip_pagination)
    clean_path = args.clean_txt or args.output_docx.with_suffix(".clean.txt")
    write_clean_text(units, clean_path)
    audit = build_audit(
        config=config,
        input_path=args.input_txt,
        output_docx=args.output_docx,
        clean_path=clean_path,
        original=original,
        cleaned=cleaned,
        units=units,
        stats=stats,
        repair_log=repair_log,
        layout=layout,
    )
    audit_path = args.audit_json or args.output_docx.with_suffix(".audit.json")
    audit_path.write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"docx": str(args.output_docx), "clean_txt": str(clean_path), "audit": str(audit_path)}, ensure_ascii=False))
    if temporary is not None:
        temporary.cleanup()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
