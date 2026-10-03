"""Behavioral gates: maps, literal evidence, cited closing and safe publication."""
from __future__ import annotations

import copy
import json
import sys
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from build_docx import build
from lesson_docx import smartart
from utils import normalize_lesson
from validate_input import validate_lesson_data


@pytest.fixture
def lesson():
    return json.loads((ROOT / "examples" / "lesson.json").read_text(encoding="utf-8"))


def test_example_build_has_real_maps_and_exact_links(lesson, tmp_path):
    output = tmp_path / "lesson.docx"
    report = build(lesson, output)
    assert report["ok"], report
    assert report["smartart_success"] == 3
    assert not report["smartart_failures"]
    with zipfile.ZipFile(output) as z:
        assert "word/diagrams/data3.xml" in z.namelist()
        assert not any(n.startswith("word/media/") for n in z.namelist())
        rels = ET.fromstring(z.read("word/_rels/document.xml.rels"))
        targets = {r.get("Target") for r in rels}
        assert "https://quran.com/39/53" in targets
        assert "https://sunnah.com/muslim:2766a" in targets


def test_missing_branch_map_blocks_publication(lesson, tmp_path):
    del lesson["sections"][0]["concept_map"]
    output = tmp_path / "lesson.docx"
    report = build(lesson, output)
    assert not report["ok"]
    assert not output.exists()
    assert any("concept_map" in e for e in report["input_errors"])


def test_all_nested_levels_are_validated(lesson):
    nested = copy.deepcopy(lesson["sections"][1]["subsections"][0])
    nested["heading"] = ""
    lesson["sections"][1]["subsections"][0]["subsections"] = [nested]
    report = validate_lesson_data(lesson)
    assert not report["ok"]
    assert any("subsections[0].subsections[0].heading" in e for e in report["errors"])


@pytest.mark.parametrize("row", [["تَوْبَةٌ"], ["تَوْبَةٌ", "نَدَمٌ", "عَزْمٌ"]])
def test_table_rows_require_exact_cell_count(lesson, row):
    lesson["sections"][0]["table"] = {"headers": ["الْحَالُ", "الْأَثَرُ"], "rows": [row]}
    assert not validate_lesson_data(lesson)["ok"]


def test_story_book_attribution_does_not_count_as_authenticity(lesson):
    lesson["closing"]["verification"].update(method="primary_text", verdict="attribution_verified")
    report = validate_lesson_data(lesson)
    assert not report["ok"]
    assert any("لا تثبت وقوعها" in e for e in report["errors"])


def test_missing_or_unverified_closing_is_rejected(lesson):
    del lesson["closing"]
    assert not validate_lesson_data(lesson)["ok"]
    assert validate_lesson_data(lesson, allow_draft=True)["ok"]


def test_unknown_field_cannot_hide_content(lesson):
    lesson["sections"][0]["paragraphs"] = ["معلومة لا يعرفها المحرك"]
    assert not validate_lesson_data(lesson)["ok"]


def test_literals_and_metadata_survive_normalization(lesson, tmp_path):
    text = "نَصٌّ مَنْقُولٌ 123 صَلَّى اللَّهُ عَلَيْهِ وَسَلَّمَ"
    lesson["sections"][1]["blocks"][0]["text"] = text
    lesson["closing"]["verification"]["source_excerpt"] = text
    normalized = normalize_lesson(lesson)
    assert normalized["sections"][1]["blocks"][0]["text"] == text
    assert normalized["closing"]["verification"]["source_excerpt"] == text
    assert normalized["sources"] == lesson["sources"]
    report = build(lesson, tmp_path / "literal.docx")
    assert report["ok"], report


def test_smartart_failure_keeps_existing_output(lesson, tmp_path, monkeypatch):
    output = tmp_path / "lesson.docx"
    original = b"existing user output"
    output.write_bytes(original)

    def fail(*args, **kwargs):
        raise smartart.SmartArtError("forced map failure")

    monkeypatch.setattr(smartart, "inject_smartart", fail)
    report = build(lesson, output)
    assert not report["ok"] and not report["built"]
    assert report["smartart_failures"]
    assert output.read_bytes() == original
    assert not list(tmp_path.glob(".lesson-build-*"))


def test_draft_is_explicit_and_never_reports_completion(lesson, tmp_path):
    del lesson["closing"]
    report = build(lesson, tmp_path / "lesson.docx", draft=True)
    assert report["built"] and report["draft"] and not report["ok"]
    assert Path(report["output"]).name == "lesson.draft.docx"
    assert not (tmp_path / "lesson.docx").exists()


def test_unverified_record_cannot_even_enter_a_draft(lesson):
    lesson["closing"]["verification"]["status"] = "unverified"
    assert not validate_lesson_data(lesson, allow_draft=True)["ok"]


def test_leaf_label_and_depth_limits_are_checked(lesson):
    lesson["sections"][0]["concept_map"]["children"][0] = "إِخْلَاصٌ " * 30
    assert not validate_lesson_data(lesson)["ok"]
    tree = {"label": "عَمَلٌ صَالِحٌ", "children": ["قَلْبٌ سَلِيمٌ"]}
    for _ in range(6):
        tree = {"label": "عَمَلٌ صَالِحٌ", "children": [tree]}
    lesson["sections"][0]["concept_map"] = tree
    assert not validate_lesson_data(lesson)["ok"]


def test_verified_primary_text_admonition_can_build(lesson, tmp_path):
    # A synthetic local book tests mechanics without attributing invented text
    # to a real scholar. Scientific source review is deliberately not simulated.
    excerpt = "مَوْعِظَةٌ تَعْلِيمِيَّةٌ لِاخْتِبَارِ الْمُحَرِّكِ."
    source_file = tmp_path / "synthetic-book-123.txt"
    source_file.write_text(excerpt, encoding="utf-8")
    lesson["sources"].append({"id": "synthetic_book", "type": "book", "title": "مصدر اصطناعي للاختبار", "author": "مؤلف المثال الاختباري", "locator": "المقطع الأول", "local_path": str(source_file)})
    lesson["closing"].update(kind="admonition", presentation="verbatim", blocks=[{"type": "evidence", "kind": "scholar_quote", "text": excerpt, "citation": "مصدر اصطناعي للاختبار، المقطع الأول", "source_id": "synthetic_book"}])
    lesson["closing"]["verification"].update(method="primary_text", verdict="attribution_verified", source_ids=["synthetic_book"], basis="سجل اصطناعي لاختبار بنية التوثيق فقط", source_excerpt=excerpt)
    report = build(lesson, tmp_path / "admonition.docx")
    assert report["ok"], report


def test_grading_method_requires_a_grading_reference_record(lesson):
    lesson["closing"]["verification"].update(method="scholar_grading", verdict="hasan")
    report = validate_lesson_data(lesson)
    assert not report["ok"]
    assert any("grading_source_id" in e for e in report["errors"])
