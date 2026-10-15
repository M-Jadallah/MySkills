from __future__ import annotations

import pytest

from validate_input import _load_config, validate_lesson_data


@pytest.fixture(scope="module")
def config():
    return _load_config(None)


FULLY_DIACRITIZED = "الْعِلْمُ نُورٌ يَهْدِي اللَّهُ بِهِ مَنْ يَشَاءُ مِنْ عِبَادِهِ فِي كُلِّ وَقْتٍ"


def _lesson(**overrides):
    lesson = {
        "title": "فَضْلُ طَلَبِ الْعِلْمِ",
        "sections": [
            {
                "heading": "فِي فَضْلِ الْعِلْمِ وَمَنْزِلَتِهِ",
                "blocks": [{"type": "paragraph", "text": FULLY_DIACRITIZED}],
                "subsections": [],
            }
        ],
    }
    for key, value in overrides.items():
        if key == "_section":
            lesson["sections"][0].update(value)
        else:
            lesson[key] = value
    return lesson


def test_valid_lesson_passes(config):
    report = validate_lesson_data(_lesson(), config)
    assert report["ok"], report["errors"]
    assert report["errors"] == []
    assert report["stats"]["sections"] == 1


def test_non_dict_root_fails(config):
    report = validate_lesson_data(["not", "a", "dict"], config)
    assert not report["ok"]
    assert any("الجذر" in e for e in report["errors"])


def test_missing_title_and_empty_sections_fail(config):
    report = validate_lesson_data({"sections": []}, config)
    assert not report["ok"]
    assert len(report["errors"]) >= 2


def test_unknown_block_type_fails(config):
    lesson = _lesson(_section={"blocks": [{"type": "quote", "text": FULLY_DIACRITIZED}]})
    report = validate_lesson_data(lesson, config)
    assert not report["ok"]
    assert any("نوع بلوك غير معروف" in e for e in report["errors"])


def test_evidence_block_counts_and_validates(config):
    lesson = _lesson(_section={"blocks": [
        {"type": "paragraph", "text": FULLY_DIACRITIZED},
        {"type": "evidence", "text": "قَالَ اللَّهُ تَعَالَى: ﴿اقْرَأْ بِاسْمِ رَبِّكَ الَّذِي خَلَقَ﴾"},
    ]})
    report = validate_lesson_data(lesson, config)
    assert report["ok"], report["errors"]
    assert report["stats"]["evidence_blocks"] == 1
    assert report["stats"]["blocks"] == 2


def test_insufficient_tashkeel_is_an_error_but_ascii_digits_only_warn(config):
    undiacritized = "العلم نور يهدي الله به من يشاء من عباده في كل وقت"
    lesson = _lesson(_section={"blocks": [{"type": "paragraph", "text": undiacritized + " في سنة 1445"}]})
    report = validate_lesson_data(lesson, config)
    assert not report["ok"], "undiacritized body text must block the build"
    assert any("التشكيل غير كافٍ" in e for e in report["errors"])
    assert any("أرقامًا إنجليزية" in w for w in report["warnings"])


def test_full_salawat_phrase_warns_not_fails(config):
    text = "قَالَ النَّبِيُّ صلى الله عليه وسلم: " + FULLY_DIACRITIZED
    report = validate_lesson_data(_lesson(_section={"blocks": [{"type": "paragraph", "text": text}]}), config)
    assert report["ok"], report["errors"]
    assert any("ﷺ" in w for w in report["warnings"])


def test_table_row_longer_than_headers_fails(config):
    lesson = _lesson(_section={
        "blocks": [],
        "table": {
            "title": "جَدْوَلٌ تَوْضِيحِيٌّ مُشَكَّلٌ بِكُلِّ حَرْفٍ",
            "headers": ["الْعَمُودُ الْأَوَّلُ الْمُشَكَّلُ", "الْعَمُودُ الثَّانِي الْمُشَكَّلُ"],
            "rows": [["قِيمَةٌ أُولَى مُشَكَّلَةٌ تَامًّا", "قِيمَةٌ ثَانِيَةٌ مُشَكَّلَةٌ", "عُنْصُرٌ زَائِدٌ مُشَكَّلٌ تَامًّا"]],
        },
    })
    report = validate_lesson_data(lesson, config)
    assert not report["ok"]
    assert any("أكبر من عدد الأعمدة" in e for e in report["errors"])


def test_concept_map_needs_label_and_children(config):
    lesson = _lesson(_section={"blocks": [], "concept_map": {"label": "طَلَبُ الْعِلْمِ"}})
    report = validate_lesson_data(lesson, config)
    assert not report["ok"]
    assert any("children" in e for e in report["errors"])


def test_concept_map_label_length_cap(config):
    long_label = "طَ" * 200
    lesson = _lesson(_section={"blocks": [], "concept_map": {"label": long_label, "children": ["فَرْعٌ مُشَكَّلٌ وَاضِحٌ"]}})
    report = validate_lesson_data(lesson, config)
    assert not report["ok"]
    assert any("الطول الأقصى" in e for e in report["errors"])


def test_nested_concept_map_children_are_checked(config):
    lesson = _lesson(_section={
        "blocks": [],
        "concept_map": {
            "label": "طَلَبُ الْعِلْمِ الْمُشَكَّلُ تَشْكِيلًا",
            "children": [
                {"label": "فَرْعٌ مُشَكَّلٌ وَاضِحٌ", "children": ["فَرْعٌ أَوَّلُ مُشَكَّلٌ", "فَرْعٌ ثَانٍ مُشَكَّلٌ"]},
            ],
        },
    })
    report = validate_lesson_data(lesson, config)
    assert report["ok"], report["errors"]
