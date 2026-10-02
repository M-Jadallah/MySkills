"""Arabic display helpers; no automatic edits to authenticated quotations."""
from __future__ import annotations

import re

MARKS = re.compile(r"[\u0610-\u061a\u064b-\u065f\u0670\u06d6-\u06ed\u08d3-\u08ff]")
LETTER = re.compile(r"[\u0621-\u063a\u0641-\u064a\u0671]")
ARABIC_INDIC = str.maketrans("0123456789", "٠١٢٣٤٥٦٧٨٩")
_SALAWAT = re.compile(r"\s+".join(
    "".join(re.escape(ch) + r"[\u064b-\u065f\u0670]*" for ch in word)
    for word in ("صلى", "الله", "عليه", "وسلم")
))


def arabic_indic_digits(text: str) -> str:
    return text.translate(ARABIC_INDIC)


def strip_tashkeel(text: str) -> str:
    return MARKS.sub("", text)


def tashkeel_coverage_ratio(text: str) -> float:
    letters = [i for i, ch in enumerate(text) if LETTER.fullmatch(ch)]
    marked = sum(i + 1 < len(text) and bool(MARKS.fullmatch(text[i + 1])) for i in letters)
    return marked / len(letters) if letters else 0.0


def normalize_prose(text: str) -> str:
    # Never guess grammatical endings or remove a possibly valid tanween.
    return arabic_indic_digits(_SALAWAT.sub("ﷺ", text))
