from __future__ import annotations

import zipfile

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH

from lesson_docx.builder import build_lesson_docx
from lesson_docx.validate import validate_docx

SAMPLE = {
    "title": "عُنْوَانُ الِاخْتِبَارِ الْمُشَكَّلُ",
    "sections": [
        {
            "heading": "مِحْوَارُ الِاخْتِبَارِ الْمُشَكَّلُ",
            "blocks": [
                {"type": "paragraph", "text": "فَقْرَةٌ مُشَكَّلَةٌ تَامَّةٌ تَشْكِيلًا كَافِيًا لِاخْتِبَارِ الْبَنَاءِ."},
                {"type": "evidence", "text": "كَلَامُنَا لَفْظٌ مُفِيدٌ كَاسْتَقَامَ … وَاسْمٌ وَفِعْلٌ ثُمَّ حَرْفُ الْكَلِمِ"},
            ],
            "subsections": [],
        }
    ],
}


def test_verse_block_is_shaded_green_centered_and_bold(tmp_path):
    out = tmp_path / "verse.docx"
    report = build_lesson_docx(SAMPLE, out)
    assert report.section_count == 1

    doc = Document(str(out))
    verse_text = SAMPLE["sections"][0]["blocks"][1]["text"]
    shaded = [p for p in doc.paragraphs if verse_text in p.text]
    assert len(shaded) == 1, "the verse text must appear in exactly one paragraph"

    p = shaded[0]
    pPr = p._p.pPr
    assert pPr is not None and pPr.find(
        "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}shd"
    ) is not None, "verse paragraph must carry a shading element"
    assert p.alignment == WD_ALIGN_PARAGRAPH.CENTER, "the verse must be rendered centered (poetic layout)"

    green_runs = [r for r in p.runs if r.font.color and r.font.color.rgb is not None and str(r.font.color.rgb) == "1F7A5B"]
    assert green_runs, "verse runs must be dark green (1F7A5B)"
    assert all(r.font.bold for r in p.runs), "verse text must be bold"


def test_verse_hemistichs_joined_with_ellipsis(tmp_path):
    out = tmp_path / "verse.docx"
    build_lesson_docx(SAMPLE, out)
    doc = Document(str(out))
    verse = SAMPLE["sections"][0]["blocks"][1]["text"]
    first, second = (h.strip() for h in verse.split("…"))
    joined = [p for p in doc.paragraphs if first in p.text and second in p.text and " … " in p.text]
    assert len(joined) == 1, "both hemistichs must appear in one line joined by ' … '"


def test_wrapped_verse_is_unwrapped(tmp_path):
    sample = {
        "title": "عُنْوَانُ الِاخْتِبَارِ الْمُشَكَّلُ",
        "sections": [
            {
                "heading": "مِحْوَارُ الِاخْتِبَارِ الْمُشَكَّلُ",
                "blocks": [
                    {"type": "evidence", "text": "«كَلَامُنَا لَفْظٌ مُفِيدٌ كَاسْتَقَامَ … وَاسْمٌ وَفِعْلٌ ثُمَّ حَرْفُ الْكَلِمِ»"}
                ],
                "subsections": [],
            }
        ],
    }
    out = tmp_path / "verse.docx"
    build_lesson_docx(sample, out)
    doc = Document(str(out))
    rendered = "\n".join(p.text for p in doc.paragraphs)
    inner = "كَلَامُنَا لَفْظٌ مُفِيدٌ كَاسْتَقَامَ … وَاسْمٌ وَفِعْلٌ ثُمَّ حَرْفُ الْكَلِمِ"
    assert inner in rendered, "the verse itself must be rendered"
    assert "«" not in rendered, "a wrapped verse must be unwrapped - no quotation marks in the verse block"


def test_verse_fill_and_no_media_in_raw_xml(tmp_path):
    out = tmp_path / "verse.docx"
    build_lesson_docx(SAMPLE, out)

    with zipfile.ZipFile(out) as zf:
        xml = zf.read("word/document.xml").decode("utf-8")
        names = zf.namelist()

    assert 'w:fill="EAF5F0"' in xml, "verse paragraph shading fill must be the light-green EAF5F0"
    assert not any(name.startswith("word/media/") for name in names), "no images allowed in lesson output"


def test_verse_document_passes_validate(tmp_path):
    out = tmp_path / "verse.docx"
    build_lesson_docx(SAMPLE, out)
    errors, warnings = validate_docx(out)
    assert errors == []
