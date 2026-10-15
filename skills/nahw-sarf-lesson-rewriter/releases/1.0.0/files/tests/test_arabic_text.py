from __future__ import annotations

from arabic_text import (
    fix_tanween_errors,
    normalize_arabic_text,
    replace_salawat_symbol,
    strip_tashkeel,
)
from utils import deep_normalize


def test_legitimate_tashkeel_is_preserved():
    text = "إنَّ الأعمالَ بالنياتِ وإنَّما لكلِّ امرئٍ ما نوى"
    assert fix_tanween_errors(text) == text


def test_correct_indefinite_noun_tanween_is_preserved():
    # The critical "don't over-correct" case: a genuinely indefinite,
    # declinable noun at the end of a phrase must keep its tanween.
    assert fix_tanween_errors("قرأتُ كتابٌ") == "قرأتُ كتابٌ"


def test_accusative_tanween_with_seat_alef_is_preserved_either_character_order():
    # تنوين النصب (accusative nunation) is conventionally spelled with a
    # trailing "seat" alef - real text uses both character orders for the
    # tanween-mark-vs-alef pair, and a shadda may also sit between them
    # (e.g. nisba adjectives like "عَمَلِيًّا"). None of this is mid-word
    # tanween; rule 1 must not strip any of it.
    assert fix_tanween_errors("نَمُوذَجًا") == "نَمُوذَجًا"  # tanween then seat alef
    assert fix_tanween_errors("نَمُوذَجاً") == "نَمُوذَجاً"  # seat alef then tanween
    assert fix_tanween_errors("عَمَلِيًّا") == "عَمَلِيًّا"  # tanween, shadda, then seat alef
    assert fix_tanween_errors("عَمَلِيّاً") == "عَمَلِيّاً"  # shadda, seat alef, then tanween
    # Negative control: tanween-kasr/damm followed by a bare alef is NOT a
    # real seat-alef spelling (only nasb/fatha tanween takes one) - this
    # must still be treated as genuinely mid-word and stripped.
    assert fix_tanween_errors("مِثَالٍا") == "مِثَالا"
    assert fix_tanween_errors("رأيتُ رجلاً") == "رأيتُ رجلاً"


def test_mid_word_tanween_is_stripped():
    # A tanween mark stuck in the middle of a word is never valid.
    assert fix_tanween_errors("كتاًب") == "كتاب"


def test_tanween_on_definite_noun_is_stripped():
    assert fix_tanween_errors("قرأتُ الكتابً") == "قرأتُ الكتاب"


def test_tanween_on_particle_is_stripped():
    assert fix_tanween_errors("ذهب منً البيت") == "ذهب من البيت"
    assert fix_tanween_errors("قال إنً ذلك حق") == "قال إن ذلك حق"


def test_tanween_on_pronoun_and_attached_conjunction_is_stripped():
    assert fix_tanween_errors("وهوً يقرأ") == "وهو يقرأ"
    assert fix_tanween_errors("فهوً رجل") == "فهو رجل"
    assert fix_tanween_errors("هوً رجل") == "هو رجل"


def test_tanween_on_definite_noun_after_a_verb_is_stripped():
    # "العالمً" is caught by the definite-article rule regardless of the
    # preceding verb "يقولُ" - there is deliberately no verb-detection rule
    # (tanween is grammatically impossible on real verbs to begin with; see
    # _is_never_tanween_eligible's docstring), so this only ever exercises
    # rule 2 (definite article), not a verb-specific check.
    assert fix_tanween_errors("يقولُ العالمً كلاماً مفيداً") == "يقولُ العالم كلاماً مفيداً"


def test_tanween_fixer_never_adds_tanween():
    # Only ever removes/relocates; a plain word with no tanween must be untouched.
    text = "هذا نص عربي بسيط بلا أخطاء"
    assert fix_tanween_errors(text) == text


def test_salawat_phrase_without_tashkeel_is_replaced():
    result = replace_salawat_symbol("قال النبي صلى الله عليه وسلم: العلم نور")
    assert result == "قال النبي ﷺ: العلم نور"
    assert "صلى الله عليه وسلم" not in result
    assert "  " not in result  # no double spaces


def test_salawat_phrase_with_ai_added_tashkeel_is_replaced():
    result = replace_salawat_symbol("قال النبي صَلَّى اللَّهُ عَلَيْهِ وَسَلَّمَ إن الأعمال بالنيات")
    assert "ﷺ" in result
    assert "صلى الله عليه وسلم" not in result
    assert strip_tashkeel("صلى الله عليه وسلم") not in strip_tashkeel(result)


def test_salawat_replacement_leaves_unrelated_text_alone():
    result = replace_salawat_symbol("هذا نص عادي عن آداب طالب العلم")
    assert "ﷺ" not in result
    assert result == "هذا نص عادي عن آداب طالب العلم"


def test_normalize_arabic_text_combines_all_steps():
    text = "قال صلى الله عليه وسلم: فهوً رجلٌ صالحٌ في سنة 1445"
    result = normalize_arabic_text(text)
    assert "ﷺ" in result
    assert "فهو رجلٌ" in result  # attached-conjunction tanween stripped, real tanween kept
    assert "١٤٤٥" in result  # ascii digits converted to Arabic-Indic
    ascii_digits = set("0123456789")
    assert not (ascii_digits & set(result))


def test_normalize_arabic_text_converts_ascii_digits():
    assert normalize_arabic_text("سنة 2024") == "سنة ٢٠٢٤"


def test_deep_normalize_applies_normalization_to_every_text_field():
    # build_docx.py runs deep_normalize over the whole lesson JSON before the
    # builder sees it - every text field must come out normalized (salawat
    # symbol, tanween fixes, Arabic-Indic digits), not just body paragraphs.
    raw = {
        "title": "الدرسً الأول",
        "subtitle": "",
        "sections": [
            {
                "heading": "قال صلى الله عليه وسلم في فضلً العلم",
                "blocks": [
                    {"type": "paragraph", "text": "إنً العلمَ نورٌ يهدي منً يشاء"},
                ],
                "subsections": [],
                "section_summary": "خلاصةٌ مفيدةٌ عنً هذا المحور",
                "table": {"title": "جدولً", "headers": ["العمودً الأول"], "rows": [["قيمةً"]]},
                "concept_map": {"label": "جذرً", "children": ["فرعً واحد"]},
            }
        ],
    }
    data = deep_normalize(raw)

    assert data["title"] == "الدرس الأول"
    section = data["sections"][0]
    assert "ﷺ" in section["heading"]
    assert "صلى الله عليه وسلم" not in section["heading"]
    assert "إنً" not in section["blocks"][0]["text"]
    assert "منً" not in section["blocks"][0]["text"]
