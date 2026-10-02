from __future__ import annotations

import zipfile

from docx import Document

from lesson_docx.builder import build_lesson_docx
from lesson_docx.validate import validate_docx

SAMPLE = {
    "title": "فَضْلُ طَلَبِ الْعِلْمِ",
    "sections": [
        {
            "heading": "فِي فَضْلِ الْعِلْمِ وَمَنْزِلَتِهِ",
            "blocks": [
                {"type": "paragraph", "text": "الْعِلْمُ عِبَادَةٌ يَقْرُبُ بِهَا الْعَبْدُ مِنْ رَبِّهِ وَأَوَّلُ وَاجِبٍ عَلَى الْمُكَلَّفِ."},
                {"type": "evidence", "text": "قَالَ اللَّهُ تَعَالَى: ﴿اقْرَأْ بِاسْمِ رَبِّكَ الَّذِي خَلَقَ﴾ [الْعَلَقُ: ١]"},
            ],
            "subsections": [],
        }
    ],
}


def test_evidence_block_is_shaded_and_green(tmp_path):
    out = tmp_path / "evidence.docx"
    report = build_lesson_docx(SAMPLE, out)
    assert report.section_count == 1

    doc = Document(str(out))
    evidence_text = SAMPLE["sections"][0]["blocks"][1]["text"]
    shaded = [p for p in doc.paragraphs if evidence_text in p.text]
    assert len(shaded) == 1, "the evidence text must appear in exactly one paragraph"

    p = shaded[0]
    pPr = p._p.pPr
    assert pPr is not None and pPr.find(
        "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}shd"
    ) is not None, "evidence paragraph must carry a shading element"

    green_runs = [r for r in p.runs if r.font.color and r.font.color.rgb is not None and str(r.font.color.rgb) == "1F7A5B"]
    assert green_runs, "non-bracket evidence runs must be dark green (1F7A5B)"
    brown_runs = [r for r in p.runs if r.font.color and r.font.color.rgb is not None and str(r.font.color.rgb) == "8B4513"]
    assert brown_runs, "bracketed spans inside evidence ([الْعَلَقُ: ١]) must stay brown"
    assert all(r.font.bold for r in p.runs), "evidence text must be bold"


def test_evidence_fill_and_no_media_in_raw_xml(tmp_path):
    out = tmp_path / "evidence.docx"
    build_lesson_docx(SAMPLE, out)

    with zipfile.ZipFile(out) as zf:
        xml = zf.read("word/document.xml").decode("utf-8")
        names = zf.namelist()

    assert 'w:fill="EAF5F0"' in xml, "evidence paragraph shading fill must be the light-green EAF5F0"
    assert not any(name.startswith("word/media/") for name in names), "no images allowed in lesson output"


def test_evidence_document_passes_validate(tmp_path):
    out = tmp_path / "evidence.docx"
    build_lesson_docx(SAMPLE, out)
    errors, warnings = validate_docx(out)
    assert errors == []
