"""Best-effort Arabic text correctness fixes applied to AI output.

Everything here is a heuristic, not a grammatical parser. Fully validating
Arabic i'rab (case marking) requires morphological analysis that is out of
scope for this bot; these functions only reduce the most common, high-
confidence tashkeel mistakes (see fix_tanween_errors docstring for exactly
which rules are applied and which are deliberately left uncovered).

All character classes below are expressed with explicit \\uXXXX escapes
(never literal Arabic characters in source) so the exact codepoints are
auditable and immune to editor/encoding round-trip surprises.
"""

from __future__ import annotations

import re

# Arabic diacritics: the 3 tanween marks + fatha/damma/kasra/shadda/sukun
# (U+064B-U+0652), plus dagger alef (U+0670, common in AI tashkeel of words
# like the dagger-alef form of "hadha"). Used to compare text "as if"
# undiacritized, e.g. to match a phrase regardless of tashkeel. Written as
# explicit \uXXXX escapes (ASCII source, no literal Arabic in the pattern
# itself) so the exact codepoints are unambiguous.
TASHKEEL_RE = re.compile("[ً-ْٰ]")

# The three tanween (nunation) marks: tanween fath (ً), tanween damm
# (ٌ), tanween kasr (ٍ).
TANWEEN_CHARS = "ًٌٍ"
TANWEEN_RE = re.compile(f"[{TANWEEN_CHARS}]")

# A "word" for our purposes: a run of Arabic base letters (U+0621-U+064A,
# which also contains tatweel U+0640) plus diacritics (U+064B-U+0652,
# U+0670). Whitespace, punctuation, digits, and Latin text are boundaries.
_ARABIC_WORD_RE = re.compile("[ء-ْٰ]+")

ARABIC_INDIC = str.maketrans("0123456789", "٠١٢٣٤٥٦٧٨٩")


def arabic_indic_digits(text: str) -> str:
    return str(text or "").translate(ARABIC_INDIC)


def strip_tashkeel(text: str) -> str:
    """Remove all Arabic diacritic marks, for diacritic-insensitive matching."""
    return TASHKEEL_RE.sub("", text or "")


# Closed-class particles/prepositions/conjunctions/adverbs that are mabni
# (indeclinable) and therefore must never carry tanween. Compared against
# each word's tashkeel-stripped form. Not exhaustive - a static list can't
# be - but covers the high-frequency function words typical in lesson
# transcripts.
_PARTICLES = {
    "من", "إلى", "الى", "عن", "على",
    "في", "حتى", "منذ", "مذ", "مع",
    "عدا", "خلا", "حاشا", "رب",
    "و", "ف", "ثم", "أو", "او", "أم", "ام",
    "لكن", "بل",
    "هل", "أ", "ما", "لا", "لم", "لما",
    "لن", "إن", "ان", "أن", "إذا", "اذا",
    "لو", "لولا",
    "قد", "إنما", "انما", "كي", "لكي",
    "حيث", "إذ", "اذ", "كأن", "لعل", "ليت",
    "إلا", "الا", "سوف", "س", "ليس", "غير",
    "سوى", "بين", "فوق", "تحت", "أمام",
    "امام", "خلف", "عند", "لدى", "قبل",
    "بعد", "دون", "نحو", "كل", "بعض",
    "إذن", "اذن", "كما", "فقط",
}
# (Set contents, spelled out: من إلى الى عن على في حتى منذ مذ مع عدا خلا حاشا رب
#  و ف ثم أو او أم ام لكن بل هل أ ما لا لم لما لن إن ان أن إذا اذا لو لولا قد إنما
#  انما كي لكي حيث إذ اذ كأن لعل ليت إلا الا سوف س ليس غير سوى بين فوق تحت أمام
#  امام خلف عند لدى قبل بعد دون نحو كل بعض إذن اذن كما فقط)

# Personal/demonstrative/relative pronouns: mabni (indeclinable), so - like
# the particles above - can never carry tanween.
_PRONOUNS = {
    "هو", "هي", "هم", "هن", "هما",
    "أنت", "انت", "أنتِ", "انتِ", "أنتم", "انتم", "أنتن", "انتن", "أنتما", "انتما",
    "أنا", "انا", "نحن",
    "هذا", "هذه", "هذان", "هذين", "هؤلاء", "ذلك", "تلك", "ذانك", "تانك", "أولئك", "اولئك",
    "الذي", "التي", "الذين", "اللذان", "اللتان", "اللاتي", "اللواتي",
}


def _strip_attached_conjunction(stripped_word: str) -> str:
    """Strip a leading wa-/fa- conjunction glued directly onto the next word.

    Arabic attaches و (wa-) and ف (fa-) directly to the following word with
    no space ("وهو", "فهو", "وقد", ...), so a bare particle/pronoun lookup
    on the raw word misses these extremely common forms. Only strips one
    leading و/ف, and only if a still-plausible (2+ letter) remainder is left,
    to avoid mangling words that just happen to start with the same letter.
    """
    if len(stripped_word) >= 3 and stripped_word[0] in "وف":
        return stripped_word[1:]
    return stripped_word


def _is_mabni_word(stripped_word: str) -> bool:
    """True if *stripped_word* itself (no conjunction stripping here - see
    _is_never_tanween_eligible, which tries this against both the raw word
    and its conjunction-stripped form) is a closed-class particle or
    pronoun - i.e. indeclinable, so it can never carry tanween."""
    return stripped_word in _PARTICLES or stripped_word in _PRONOUNS


def _is_definite(stripped_word: str) -> bool:
    """A word carrying the definite article (al-) prefix.

    Tanween marks indefiniteness, so it can never co-occur with the definite
    article - this is one of the most reliable, exception-free rules in
    Arabic grammar, no morphology needed.
    """
    return len(stripped_word) >= 3 and stripped_word[:2] == "ال"


def _is_never_tanween_eligible(stripped_word: str) -> bool:
    """True if *stripped_word* can never legitimately carry tanween.

    Checks the word as-is AND with one leading wa-/fa- conjunction peeled
    off, since و/ف attach directly with no space (e.g. "والسنة", "فيقول")
    and both of the underlying checks (definite article, mabni
    particle/pronoun) need to see past that attachment to fire correctly.

    Deliberately has no "verb-like" check. An earlier version flagged words
    starting with a mudari' prefix letter (ي/ت/ن/أ) as verb-like and
    stripped their trailing tanween - but tanween is grammatically a
    NOMINAL-only phenomenon (real Arabic verbs never take ً/ٌ/ٍ in any
    tense or mood; the sound-alike "confirming nun" suffix is a distinct
    attached consonant, not one of these diacritics). So a word actually
    carrying tanween can never be a genuine finite verb to begin with,
    which means that heuristic could only ever be firing on ordinary nouns
    that happen to start with one of those four extremely common letters
    (e.g. "أُسْلُوبٌ", "نَمُوذَجٌ", "تَعْلِيمٌ", "يَنْبُوعٌ") - a large false-positive
    surface for a grammatically-impossible error class. Removed rather than
    patched with more per-pattern exceptions.
    """
    candidates = {stripped_word, _strip_attached_conjunction(stripped_word)}
    return any(_is_definite(w) or _is_mabni_word(w) for w in candidates)


def fix_tanween_errors(text: str) -> str:
    """Best-effort cleanup of common tanween (nunation) placement mistakes.

    Rules applied per Arabic word span, in order:
      1. A tanween mark with a base letter (not just another diacritic)
         somewhere after it is genuinely mid-word; strip it. Two exceptions,
         both real spelling conventions rather than mid-word placement:
         (a) a tanween followed only by more diacritics (e.g. combined with
         a shadda on the final letter - AI/user text isn't always
         consistent about whether shadda or tanween comes first), and
          (b) tanween-fatha (ً) immediately followed by exactly one bare
          alef or alef maqsura and nothing else - the conventional "seat"
          of accusative nunation (تنوين النصب), e.g. "طَلَبًا" and "مَعْنًى".
          Left for rules 2-3 to judge on its own merits.
      2. Tanween on a word carrying the definite article (al-) is stripped -
         definiteness and nunation are mutually exclusive, no exceptions.
      3. Tanween on a known indeclinable particle or pronoun is stripped,
         including one with a leading wa-/fa- conjunction glued onto it
         (e.g. "وهو", "فهو").
    There is deliberately no verb-detection rule: tanween is a nominal-only
    phenomenon in Arabic (real verbs never take it, in any tense or mood),
    so a word that already carries tanween cannot be a genuine verb -
    nothing here needs to "protect" verbs from nunation. Only ever removes
    tanween marks - never adds one, and never touches non-tanween
    diacritics. This will not catch every incorrect placement (e.g.
    tanween wrongly kept on some other non-declinable noun) - that requires
    morphological parsing which is out of scope; this is a best-effort
    reduction, not a guarantee.
    """

    def _fix_word(match: "re.Match[str]") -> str:
        word = match.group(0)
        if not TANWEEN_RE.search(word):
            return word

        # Rule 1: strip any tanween that has a base letter after it
        # anywhere later in the word - that's genuinely mid-word. Two
        # exceptions (see docstring): a tanween with only more diacritics
        # after it, and tanween-fatha followed by any run of diacritics
        # (e.g. a shadda, common on nisba adjectives like "عَمَلِيًّا") and then
        # exactly one bare seat alef with nothing after it - the
        # accusative-nunation spelling convention, however many diacritics
        # happen to be stacked between the tanween mark and the seat alef.
        chars = list(word)
        for i, ch in enumerate(chars):
            if ch not in TANWEEN_CHARS:
                continue
            rest = chars[i + 1 :]
            if ch == "ً" and rest[-1:] in (["ا"], ["ى"]) and all(TASHKEEL_RE.match(c) for c in rest[:-1]):
                continue
            if any(not TASHKEEL_RE.match(c) for c in rest):
                chars[i] = ""
        word = "".join(chars)

        # Rules 2-3: a trailing tanween (now guaranteed, after rule 1, to
        # be part of the final letter's diacritic cluster regardless of
        # its position relative to e.g. a combined shadda) on a definite
        # noun or particle/pronoun is always wrong.
        trailing_match = TANWEEN_RE.search(word)
        if trailing_match:
            stripped = strip_tashkeel(word)
            if _is_never_tanween_eligible(stripped):
                idx = trailing_match.start()
                word = word[:idx] + word[idx + 1 :]

        return word

    return _ARABIC_WORD_RE.sub(_fix_word, text or "")


SALAWAT_SYMBOL = "ﷺ"  # ARABIC LIGATURE SALLALLAHOU ALAYHE WASALLAM
# Plain (undiacritized) words of the phrase, as explicit codepoints:
# صلى = "sad-lam-alef-maqsura" (salla)
# الله = "Allah"
# عليه = "alayhi"
# وسلم = "wasallam"
_SALAWAT_PLAIN_WORDS = [
    "صلى",
    "الله",
    "عليه",
    "وسلم",
]


def _tashkeel_tolerant_word_pattern(word: str) -> str:
    """Regex matching *word* with any amount of tashkeel after each letter."""
    tashkeel_opt = "[ً-ْٰ]*"
    return tashkeel_opt.join(re.escape(ch) for ch in word) + tashkeel_opt


_SALAWAT_RE = re.compile(
    r"[ \t]*" + r"\s+".join(_tashkeel_tolerant_word_pattern(w) for w in _SALAWAT_PLAIN_WORDS) + r"[ \t]*"
)


def replace_salawat_symbol(text: str) -> str:
    """Replace the full phrase 'salla Allahu alayhi wa sallam' (with or
    without AI-added tashkeel) with the ﷺ symbol.

    Matches the phrase regardless of whatever diacritics the model attached
    to it, and normalizes the surrounding whitespace to a single space on
    each side so no double spaces or awkward punctuation spacing result.
    Trailing punctuation immediately after the phrase (e.g. a colon) is left
    untouched since the match never consumes non-Arabic-letter characters.
    """
    text = text or ""
    if not text:
        return text
    replaced = _SALAWAT_RE.sub(f" {SALAWAT_SYMBOL} ", text)
    replaced = re.sub(r"[ \t]+", " ", replaced)
    replaced = re.sub("[ \t]+([.,،؛:!؟])", r"\1", replaced)
    return replaced.strip()


def tashkeel_coverage_ratio(text: str) -> float:
    """Rough estimate of how much of *text*'s Arabic letters carry a tashkeel mark.

    Heuristic only, like everything else in this module - not grammatical
    validation. Counts Arabic base letters (excluding tatweel U+0640, which
    is never diacritized itself) that are immediately followed by at least
    one mark in TASHKEEL_RE, divided by the total count of such base
    letters. Returns 0.0 for text with no Arabic base letters at all (never
    raises ZeroDivisionError). Intended as a coverage *signal* for tests and
    observability - e.g. to notice a field the AI silently left bare - not a
    claim that the diacritics present are grammatically correct.
    """
    text = text or ""
    base_letters = 0
    diacritized_letters = 0
    length = len(text)
    for i, ch in enumerate(text):
        if ch == "ـ" or TASHKEEL_RE.match(ch):
            continue
        if not _ARABIC_WORD_RE.match(ch):
            continue
        base_letters += 1
        if i + 1 < length and TASHKEEL_RE.match(text[i + 1]):
            diacritized_letters += 1
    if base_letters == 0:
        return 0.0
    return diacritized_letters / base_letters


def normalize_arabic_text(text: str) -> str:
    """Single entry point: salawat replacement, tanween cleanup, then digits.

    Order matters - the salawat phrase is replaced before tanween cleanup so
    any tashkeel the model attached to it never reaches (and can't confuse)
    the tanween heuristics.
    """
    text = replace_salawat_symbol(text or "")
    text = fix_tanween_errors(text)
    text = arabic_indic_digits(text)
    return text
