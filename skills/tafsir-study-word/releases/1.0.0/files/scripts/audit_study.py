#!/usr/bin/env python3
"""Check mechanically verifiable invariants of a sourced Arabic tafsir study.

A clean report does NOT certify complete scientific coverage, sound judgments,
correct vocalization, authentic quotations from the underlying printed books,
or visual Word layout. Those require the documented human/agent reviews.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import unicodedata
import zipfile
from collections import Counter
from pathlib import Path
from urllib.parse import urlparse
from xml.etree import ElementTree as ET

KEY = re.compile(r"^[1-9][0-9]{0,2}:[1-9][0-9]{0,2}$")
W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def normalized(text: str) -> str:
    """Comparison only: do not fold hamza, ya/alif maqsura, ta marbuta, or letters."""
    return "".join(c for c in unicodedata.normalize("NFC", text)
                   if c != "ـ" and not unicodedata.category(c).startswith(("M", "P", "Z", "C")))


def sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def present(value) -> bool:
    return isinstance(value, str) and bool(value.strip())


def displayed(text: str) -> str:
    """Preserve every printed letter, mark, digit and punctuation sign.

    Word represents soft line breaks differently from JSON newlines; only
    whitespace is ignored here. Source matching deliberately uses normalized
    instead, because adding reviewed vowels to an unvocalized source is allowed.
    """
    return re.sub(r'\s+', '', unicodedata.normalize('NFC', text))


def display_contract(study):
    """Yield only reader-facing fields; exclude ids, URLs and workflow metadata."""
    def fields(obj, path, names):
        for name in names:
            if present(obj.get(name)):
                yield path + '.' + name, obj[name]

    yield from fields(study, 'study', ('title', 'subtitle'))
    for i, value in enumerate(study.get('methodology', [])):
        if present(value):
            yield f'study.methodology[{i}]', value
    sources = {s['id']: s for s in study.get('sources', [])}
    for i, source in enumerate(study.get('sources', [])):
        yield from fields(source, f'study.sources[{i}]', ('name', 'author', 'bibliographic_note'))
    for vi, v in enumerate(study.get('verses', [])):
        vp = f'study.verses[{vi}]'
        yield from fields(v, vp, ('heading', 'text'))
        yield from fields(v.get('summary', {}), vp + '.summary', ('text', 'citation'))
        for axis, text in v.get('empty_axes', {}).items():
            if present(text):
                yield vp + '.empty_axes.' + axis, text
        quotes = {}
        for gi, group in enumerate(v.get('groups', [])):
            gp = f'{vp}.groups[{gi}]'
            yield from fields(group, gp, ('title', 'note'))
            for qi, q in enumerate(group.get('quotes', [])):
                quotes[q.get('id')] = q
                yield from fields(q, f'{gp}.quotes[{qi}]', ('text', 'owner', 'citation'))
                source = sources.get(q.get('source_id'), {})
                if not q.get('citation'):
                    yield from fields(source, f'{gp}.quotes[{qi}].source', ('name',))
            for pi, pref in enumerate(group.get('preferences', [])):
                pp = f'{gp}.preferences[{pi}]'
                yield from fields(pref, pp, ('text', 'reason'))
                yield from fields(sources.get(pref.get('source_id'), {}), pp + '.source', ('name', 'author'))
        for ti, term in enumerate(v.get('terms', [])):
            tp = f'{vp}.terms[{ti}]'
            yield from fields(term, tp, ('name', 'field', 'definition', 'explanation', 'example'))
            for qid in term.get('source_quote_ids', []):
                source = sources.get(quotes.get(qid, {}).get('source_id'), {})
                yield from fields(source, tp + '.source', ('name',))
        for si, story in enumerate(v.get('stories', [])):
            sp = f'{vp}.stories[{si}]'
            yield from fields(story, sp, ('classification', 'judgment', 'evidence'))
            yield from fields(story.get('quote', {}), sp + '.quote', ('text', 'owner', 'citation'))
        for ti, theme in enumerate(v.get('themes', [])):
            tp = f'{vp}.themes[{ti}]'
            yield from fields(theme, tp, ('title', 'explanation'))
            for genre, names in (('quran', ('text', 'citation')), ('hadith', ('text', 'narrator', 'reference', 'grade', 'grade_source')), ('poetry', ('text', 'author', 'reference', 'attribution_note'))):
                for pi, proof in enumerate(theme.get(genre, [])):
                    yield from fields(proof, f'{tp}.{genre}[{pi}]', names)
        for bi, benefit in enumerate(v.get('benefits', [])):
            yield from fields(benefit, f'{vp}.benefits[{bi}]', ('text',))
        for ni, value in enumerate(v.get('names', {}).get('paragraphs', [])):
            if present(value):
                yield f'{vp}.names.paragraphs[{ni}]', value
        for ni, ref in enumerate(v.get('names', {}).get('references', [])):
            yield from fields(ref, f'{vp}.names.references[{ni}]', ('text',))
    for bi, ref in enumerate(study.get('bibliography', [])):
        yield from fields(ref, f'study.bibliography[{bi}]', ('text',))


class Auditor:
    def __init__(self, study: dict, sources: dict, quran: dict, coverage: dict):
        self.study, self.manifest, self.quran, self.coverage = study, sources, quran, coverage
        self.errors, self.warnings = [], []
        self.sources, self.blocks, self.output_ids, self.quote_records = {}, {}, {}, []
        self.verse_keys, self.docx_texts, self.docx_quran_texts = set(), [], []

    def error(self, code: str, path: str, message: str):
        self.errors.append({"code": code, "path": path, "message": message})

    def warning(self, code: str, path: str, message: str):
        self.warnings.append({"code": code, "path": path, "message": message})

    def text(self, obj: dict, key: str, path: str) -> bool:
        if not present(obj.get(key)):
            self.error("required_text", f"{path}.{key}", "A nonempty text value is required")
            return False
        return True

    def objects(self, obj: dict, key: str, path: str) -> list:
        value = obj.get(key)
        if not isinstance(value, list):
            self.error("required_array", f"{path}.{key}", "An array is required, including when empty")
            return []
        output = []
        for index, item in enumerate(value):
            if not isinstance(item, dict):
                self.error("object_type", f"{path}.{key}[{index}]", "An object is required")
            else:
                output.append(item)
        return output

    def register(self, obj: dict, path: str):
        identifier = obj.get("id")
        if not present(identifier):
            self.error("missing_id", path, "Output object requires a stable id")
        elif identifier in self.output_ids:
            self.error("duplicate_id", path, f"Duplicate output id {identifier}")
        else:
            self.output_ids[identifier] = path

    def url(self, value, path: str, required=False):
        if value in (None, "") and not required:
            return
        if not isinstance(value, str) or urlparse(value).scheme not in ("https", "http") or not urlparse(value).netloc:
            self.error("invalid_url", path, "A complete HTTP(S) verification URL is required")

    def check_manifest(self):
        if self.manifest.get("schema_version") != 1:
            self.error("schema_version", "sources", "Expected schema_version 1")
        for si, source in enumerate(self.objects(self.manifest, "sources", "sources")):
            path = f"sources.sources[{si}]"
            sid = source.get("id")
            if not present(sid) or sid in self.sources:
                self.error("source_id", path, "Source id must be nonempty and unique")
                continue
            self.sources[sid] = source
            self.text(source, "name", path)
            raw = source.get("raw_text")
            if not isinstance(raw, str):
                self.error("raw_text", path, "raw_text must be a string")
                continue
            if not raw.strip():
                self.error("empty_source", path, "Source contains no non-whitespace text")
            if source.get("raw_text_sha256") and sha256(raw) != source["raw_text_sha256"]:
                self.error("raw_text_hash", path, "raw_text no longer matches its UTF-8 text digest")
            if not re.fullmatch(r"[0-9a-f]{64}", str(source.get("sha256", ""))):
                self.error("source_hash", path, "Original byte SHA256 is missing or malformed")
            source_path = source.get("path")
            if present(source_path):
                file = Path(source_path)
                if file.is_file():
                    original = file.read_bytes()
                    if hashlib.sha256(original).hexdigest() != source.get("sha256"):
                        self.error("source_file_changed", path, "The original file has changed since ingestion")
                    encoding = source.get("encoding")
                    if present(encoding):
                        try:
                            if original.decode(encoding, errors="strict") != raw:
                                self.error("raw_origin_mismatch", path, "Embedded raw_text differs from decoding the original file")
                        except (UnicodeError, LookupError) as exc:
                            self.error("source_encoding", path, str(exc))
                else:
                    self.warning("source_file_unavailable", path, "Original path unavailable; embedded raw_text is still audited")
            previous_end = 0
            for bi, block in enumerate(self.objects(source, "blocks", path)):
                bp = f"{path}.blocks[{bi}]"
                bid = block.get("id")
                pair = (sid, bid)
                if not present(bid) or pair in self.blocks:
                    self.error("block_id", bp, "Block id must be nonempty and unique within its source")
                    continue
                self.blocks[pair] = block
                start, end = block.get("start"), block.get("end")
                if type(start) is not int or type(end) is not int or not (0 <= start <= end <= len(raw)):
                    self.error("block_span", bp, "Invalid absolute Unicode-codepoint block span")
                    continue
                if start < previous_end:
                    self.error("block_overlap", bp, "Source blocks overlap or are out of order")
                previous_end = end
                if block.get("text") != raw[start:end]:
                    self.error("block_text", bp, "Block text must equal raw_text[start:end] exactly")
                if block.get("sha256") != sha256(raw[start:end]):
                    self.error("block_hash", bp, "Block digest does not match the original slice")
                self.block_keys(block, bp)

    def block_keys(self, block: dict, path: str) -> set[str]:
        explicit = block.get("verse_keys", [])
        numbers = block.get("verses", [])
        if not isinstance(explicit, list) or any(not isinstance(k, str) or not KEY.fullmatch(k) for k in explicit):
            self.error("block_verse_keys", path, "verse_keys must contain valid surah:verse keys")
            explicit = []
        if not isinstance(numbers, list) or any(type(v) is not int or v < 1 or v > 286 for v in numbers):
            self.error("block_verses", path, "verses must contain positive integer verse numbers")
            numbers = []
        surah_obj = self.study.get("surah")
        surah = surah_obj.get("number") if isinstance(surah_obj, dict) else None
        inferred = {f"{surah}:{v}" for v in numbers} if type(surah) is int else set()
        if explicit and numbers and {int(k.split(':')[1]) for k in explicit} != set(numbers):
            self.error("inconsistent_block_mapping", path, "verse_keys and verses disagree")
        return set(explicit) or inferred

    def quote(self, quote: dict, path: str, verse_key: str, register=True):
        if register:
            self.register(quote, path)
        good_text = self.text(quote, "text", path)
        sid, bid = quote.get("source_id"), quote.get("block_id")
        source, block = self.sources.get(sid), self.blocks.get((sid, bid))
        if source is None:
            self.error("quote_source", path, "Quotation names a nonexistent source_id")
            return
        if block is None:
            self.error("quote_block", path, "Quotation must name an existing block of that exact source")
            return
        keys = self.block_keys(block, path)
        if keys and verse_key not in keys and not present(quote.get("cross_reference_reason")):
            self.error("quote_verse", path, "Quotation lies outside this verse's mapped source block; explain an intentional cross-reference")
        spans = quote.get("source_spans")
        comparison = None
        if spans is None:
            comparison = block.get("text", "")
            self.warning("quote_without_spans", path, "Only in-block substring matching is available; record exact spans for traceability")
        elif not isinstance(spans, list) or not spans:
            self.error("quote_spans", path, "source_spans must be a nonempty ordered array")
        else:
            pieces, previous_end, valid = [], -1, True
            if len(spans) > 1:
                self.warning("omission_review_required", path, "Multiple source spans require review that omissions remove only approved isnads/footnotes, not meaningful content")
            for i, span in enumerate(spans):
                if not isinstance(span, dict):
                    self.error("quote_span", f"{path}.source_spans[{i}]", "A span object is required")
                    valid = False
                    continue
                start, end = span.get("start"), span.get("end")
                if type(start) is not int or type(end) is not int or not (
                        type(block.get("start")) is int and type(block.get("end")) is int
                        and block["start"] <= start < end <= block["end"]
                        and 0 <= start < end <= len(source["raw_text"])):
                    self.error("quote_span", f"{path}.source_spans[{i}]", "Span must lie wholly inside the named block and source")
                    valid = False
                    continue
                if start < previous_end:
                    self.error("quote_span_order", path, "Source spans overlap or are out of order")
                    valid = False
                previous_end = end
                pieces.append(source["raw_text"][start:end])
            if valid:
                comparison = "".join(pieces)
        if good_text and comparison is not None:
            expected, actual = normalized(comparison), normalized(quote["text"])
            matches = actual == expected if spans is not None else bool(actual) and actual in expected
            if not matches:
                self.error("literal_mismatch", path, "Quotation letters differ from the named source/block/spans")
        self.url(quote.get("url"), f"{path}.url")
        if good_text:
            self.docx_texts.append((path, quote["text"]))
        if register:
            self.quote_records.append((quote.get("id"), sid, bid, verse_key, path))

    def quran_text(self, entry: dict, path: str):
        key, text = entry.get("key"), entry.get("text")
        if not isinstance(key, str) or not KEY.fullmatch(key):
            self.error("quran_key", path, "Expected a surah:verse key")
            return
        canonical = self.quran.get(key)
        if isinstance(canonical, dict):
            canonical = canonical.get("text")
        if not present(text) or not present(canonical):
            self.error("quran_missing", path, "A nonempty verse and its canonical reference are required")
        elif unicodedata.normalize("NFC", text).strip() != unicodedata.normalize("NFC", canonical).strip():
            self.error("quran_mismatch", path, "Quran text must match the supplied verified Quran verbatim, including diacritics")
        if present(text):
            self.docx_quran_texts.append((path, text))
        self.url(entry.get("url"), f"{path}.url")

    def summary_policy(self, summary: dict, key: str, path: str):
        primary = {sid for sid, source in self.sources.items()
                   if "المختصر" in normalized(source.get("name", ""))}
        available = {sid for (sid, _), block in self.blocks.items()
                     if sid in primary and key in self.block_keys(block, path)}
        sid = summary.get("source_id")
        if primary:
            if not available:
                authorization = summary.get("fallback_authorization")
                approved = (isinstance(authorization, dict)
                            and authorization.get("authority") == "user"
                            and present(authorization.get("instruction"))
                            and isinstance(authorization.get("verse_keys"), list)
                            and key in authorization["verse_keys"])
                if not approved:
                    self.error("primary_coverage_gap", path, "Al-Mukhtasar file exists but lacks a mapped entry for this verse; explicit recorded user authorization is required for a fallback")
                    return
                self.warning("authorized_primary_gap", path, "A recorded human instruction permits fallback for this verse; verify that the instruction is authentic and applicable")
                source_name = normalized(self.sources.get(sid, {}).get("name", ""))
                if "السعدي" not in source_name:
                    self.error("summary_fallback_source", path, "The approved fallback is Al-Sa'di")
                if not present(summary.get("fallback_reason")):
                    self.error("summary_fallback_reason", path, "Record the primary coverage gap")
            elif sid not in available:
                self.error("summary_primary_source", path, "Al-Mukhtasar is available for this verse and must supply the summary")
        else:
            source_name = normalized(self.sources.get(sid, {}).get("name", ""))
            if "السعدي" not in source_name:
                self.error("summary_fallback_source", path, "When Al-Mukhtasar is absent, the approved fallback is Al-Sa'di")
            if not present(summary.get("fallback_reason")):
                self.error("summary_fallback_reason", path, "Record why the primary source is absent for this verse")

    def check_study(self):
        if self.study.get("schema_version") != 1:
            self.error("schema_version", "study", "Expected schema_version 1")
        for field in ("title", "subtitle"):
            self.text(self.study, field, "study")
        surah = self.study.get("surah")
        multi = self.study.get('surahs')
        if multi is not None:
            surah_objects = self.objects(self.study, 'surahs', 'study')
            if not surah_objects:
                self.error('surahs_empty', 'study.surahs', 'At least one verified surah is required')
            surah = surah_objects[0] if surah_objects else {}
        else:
            surah_objects = [surah] if isinstance(surah, dict) else []
        if not isinstance(surah, dict):
            self.error("surah", "study.surah", "A surah object is required")
            surah = {}
        if type(surah.get("number")) is not int or not 1 <= surah.get("number", 0) <= 114:
            self.error("surah_number", "study.surah", "Surah number must be in 1..114")
        self.text(surah, "name", "study.surah")
        allowed_surahs = set()
        for si, item in enumerate(surah_objects):
            number = item.get('number')
            if type(number) is not int or not 1 <= number <= 114 or number in allowed_surahs:
                self.error('surah_number', f'study.surahs[{si}]', 'Surah numbers must be valid and unique')
            allowed_surahs.add(number)
            self.text(item, 'name', f'study.surahs[{si}]')
        methodology = self.study.get("methodology")
        if not isinstance(methodology, list) or not methodology or any(not present(t) for t in methodology):
            self.error("methodology", "study.methodology", "A nonempty list of methodology paragraphs is required")
        catalog = self.objects(self.study, "sources", "study")
        catalog_ids = set()
        for i, source in enumerate(catalog):
            path = f"study.sources[{i}]"
            if source.get("id") not in self.sources:
                self.error("catalog_source", path, "Source id does not exist in the manifest")
            if source.get("id") in catalog_ids:
                self.error("catalog_duplicate", path, "Source catalog repeats an id")
            catalog_ids.add(source.get("id"))
            self.text(source, "name", path)
            self.text(source, "author", path)
        if catalog_ids != set(self.sources):
            self.error("catalog_coverage", "study.sources", "The study catalog must account for every supplied source")
        verses = self.objects(self.study, "verses", "study")
        if not verses:
            self.error("no_verses", "study.verses", "At least one studied verse is required")
        for vi, verse in enumerate(verses):
            path, key = f"study.verses[{vi}]", verse.get("key")
            if not isinstance(key, str) or not KEY.fullmatch(key):
                self.error("verse_key", path, "A valid surah:verse key is required")
                key = "invalid"
            if key in self.verse_keys:
                self.error("duplicate_verse", path, "A verse key is repeated")
            self.verse_keys.add(key)
            if key != "invalid" and int(key.split(":")[0]) not in allowed_surahs:
                self.error("verse_surah", path, "Main verse belongs to another surah")
            self.text(verse, "heading", path)
            self.quran_text(verse, path)
            empty = verse.get("empty_axes", {})
            if not isinstance(empty, dict):
                self.error("empty_axes", path, "empty_axes must be an object of explicit non-applicability explanations")
                empty = {}
            for axis in empty:
                if axis not in ("2", "3", "4", "5", "6") or not present(empty[axis]):
                    self.error("empty_axis_reason", path, "Only axes 2..6 may be empty, with a nonempty reason")
            summary = verse.get("summary")
            if not isinstance(summary, dict):
                self.error("missing_axis_1", path, "Axis 1 requires a sourced summary object")
            else:
                if summary.get("mode") not in ("literal", "extracted"):
                    self.error("summary_mode", path, "Summary mode must be literal or extracted")
                self.quote(summary, f"{path}.summary", key, register=False)
                self.summary_policy(summary, key, f"{path}.summary")
            for field, axis in (("groups", "2"), ("terms", "3"), ("stories", "4"),
                                ("themes", "5"), ("benefits", "6")):
                values = self.objects(verse, field, path)
                if not values and not present(empty.get(axis)):
                    self.error(f"missing_axis_{axis}", path, f"Axis {axis} is empty without a reason")
                for i, obj in enumerate(values):
                    op = f"{path}.{field}[{i}]"
                    self.register(obj, op)
                    if field == "groups":
                        self.text(obj, "title", op)
                        quotes = self.objects(obj, "quotes", op)
                        if not quotes:
                            self.error("empty_group", op, "Every opinion group requires literal source quotations")
                        for qi, quote in enumerate(quotes):
                            self.quote(quote, f"{op}.quotes[{qi}]", key)
                        for pi, pref in enumerate(self.objects(obj, "preferences", op)):
                            pp = f"{op}.preferences[{pi}]"
                            if pref.get("source_id") not in self.sources:
                                self.error("preference_source", pp, "Preference source does not exist")
                            for required in ("text", "reason"):
                                self.text(pref, required, pp)
                                if present(pref.get(required)):
                                    self.docx_texts.append((f"{pp}.{required}", pref[required]))
                            if not isinstance(pref.get("quote_ids"), list) or not pref.get("quote_ids"):
                                self.error("preference_evidence", pp, "A preference requires supporting quotation ids")
                    elif field == "terms":
                        for required in ("name", "field", "definition", "explanation", "example"):
                            self.text(obj, required, op)
                            if present(obj.get(required)):
                                self.docx_texts.append((f"{op}.{required}", obj[required]))
                        if not isinstance(obj.get("source_quote_ids"), list) or not obj.get("source_quote_ids"):
                            self.error("term_source", op, "A term requires ids of source quotations where it occurs")
                    elif field == "stories":
                        quote = obj.get("quote")
                        if not isinstance(quote, dict):
                            self.error("story_quote", op, "A story requires its literal sourced quotation")
                        else:
                            self.quote(quote, f"{op}.quote", key)
                        for required in ("classification", "judgment", "evidence"):
                            self.text(obj, required, op)
                    elif field == "themes":
                        for required in ("title", "explanation"):
                            self.text(obj, required, op)
                        proofs = self.objects(obj, "quran", op)
                        hadiths = self.objects(obj, "hadith", op)
                        poems = self.objects(obj, "poetry", op)
                        if not proofs and not hadiths and not poems:
                            self.error("empty_theme_evidence", op, "A theme needs source evidence, or it must be omitted with an explanation")
                        for genre, values in (("quran", proofs), ("hadith", hadiths), ("poetry", poems)):
                            if not values:
                                self.error(f"theme_missing_{genre}", op, f"Every theme requires the requested Quran, hadith, and poetry genres; {genre} is empty")
                        for qi, proof in enumerate(proofs):
                            self.quran_text(proof, f"{op}.quran[{qi}]")
                            self.text(proof, "citation", f"{op}.quran[{qi}]")
                        for hi, hadith in enumerate(hadiths):
                            hp = f"{op}.hadith[{hi}]"
                            for required in ("text", "narrator", "reference", "grade", "grade_source"):
                                self.text(hadith, required, hp)
                            if type(hadith.get("excerpt")) is not bool:
                                self.error("hadith_excerpt", hp, "excerpt must explicitly be true or false")
                            self.url(hadith.get("url"), f"{hp}.url", required=True)
                            if present(hadith.get("text")):
                                self.docx_texts.append((hp, hadith["text"]))
                        for pi, poem in enumerate(poems):
                            pp = f"{op}.poetry[{pi}]"
                            for required in ("text", "author", "reference", "attribution_note"):
                                self.text(poem, required, pp)
                            self.url(poem.get("url"), f"{pp}.url", required=True)
                            if present(poem.get("text")):
                                self.docx_texts.append((pp, poem["text"]))
                    elif field == "benefits":
                        self.text(obj, "text", op)
                        if obj.get("type") not in ("direct", "inferred"):
                            self.error("benefit_type", op, "Benefit type must be direct or inferred")
                        if not isinstance(obj.get("evidence_ids"), list) or not obj.get("evidence_ids"):
                            self.error("benefit_evidence", op, "A benefit requires traceable evidence ids")
            names = verse.get("names")
            if not isinstance(names, dict) or not isinstance(names.get("paragraphs"), list) or not names.get("paragraphs") or any(not present(p) for p in names.get("paragraphs", [])):
                self.error("missing_axis_7", path, "Axis 7 always needs explicit paragraphs, including a reason when no name occurs")
            else:
                for ni, paragraph in enumerate(names["paragraphs"]):
                    self.docx_texts.append((f"{path}.names.paragraphs[{ni}]", paragraph))
                for ni, ref in enumerate(self.objects(names, "references", f"{path}.names")):
                    self.text(ref, "text", f"{path}.names.references[{ni}]")
                    self.url(ref.get("url"), f"{path}.names.references[{ni}].url")
        for bi, ref in enumerate(self.objects(self.study, "bibliography", "study")):
            self.text(ref, "text", f"study.bibliography[{bi}]")
            self.url(ref.get("url"), f"study.bibliography[{bi}].url")
        self.check_output_links(verses)

    def check_output_links(self, verses: list):
        quote_sources = {qid: sid for qid, sid, _, _, _ in self.quote_records}
        for vi, verse in enumerate(verses):
            path = f"study.verses[{vi}]"
            for gi, group in enumerate(verse.get("groups", [])):
                if not isinstance(group, dict):
                    continue
                for pi, pref in enumerate(group.get("preferences", [])):
                    if not isinstance(pref, dict):
                        continue
                    for qid in pref.get("quote_ids", []) if isinstance(pref.get("quote_ids"), list) else []:
                        if qid not in quote_sources:
                            self.error("broken_preference_link", f"{path}.groups[{gi}].preferences[{pi}]", f"Unknown output id {qid}")
                        elif quote_sources[qid] != pref.get("source_id"):
                            self.error("preference_source_mismatch", f"{path}.groups[{gi}].preferences[{pi}]", "Preference evidence must belong to the stated preferring source")
            for field, linkfield in (("terms", "source_quote_ids"), ("benefits", "evidence_ids")):
                for i, obj in enumerate(verse.get(field, [])):
                    if not isinstance(obj, dict):
                        continue
                    for oid in obj.get(linkfield, []) if isinstance(obj.get(linkfield), list) else []:
                        if field == "terms" and oid not in quote_sources:
                            self.error("term_not_a_quote", f"{path}.{field}[{i}]", f"Term evidence must name a quotation id, not {oid}")
                        if oid not in self.output_ids and oid not in self.verse_keys:
                            self.error("broken_evidence_link", f"{path}.{field}[{i}]", f"Unknown output id {oid}")

    def check_coverage(self):
        items = self.objects(self.coverage, "items", "coverage")
        by_id, pairs = {}, {}
        for ci, item in enumerate(items):
            path = f"coverage.items[{ci}]"
            cid, pair = item.get("id"), (item.get("source_id"), item.get("block_id"))
            if not present(cid) or cid in by_id:
                self.error("coverage_id", path, "Coverage id must be unique and nonempty")
            else:
                by_id[cid] = item
            block = self.blocks.get(pair)
            if block is None:
                self.error("coverage_source_block", path, "Coverage refers to an unknown source/block pair")
                continue
            pairs.setdefault(pair, []).append(item)
            keys = item.get("verse_keys")
            if not isinstance(keys, list) or any(not isinstance(k, str) or not KEY.fullmatch(k) for k in keys):
                self.error("coverage_keys", path, "verse_keys must be an array of valid keys")
                keys = []
            mapped = self.block_keys(block, path)
            if mapped and any(k not in mapped for k in keys):
                self.error("coverage_wrong_verse", path, "Coverage verse is outside the source block mapping")
            status = item.get("status")
            if status not in ("included", "duplicate", "shared", "not_relevant"):
                self.error("coverage_status", path, "Unknown coverage decision")
            self.text(item, "kind", path)
            outputs = item.get("output_ids")
            if not isinstance(outputs, list) or any(not isinstance(i, str) for i in outputs):
                self.error("coverage_outputs", path, "output_ids must be an array of output ids")
                outputs = []
            for oid in outputs:
                if oid not in self.output_ids and oid not in self.verse_keys:
                    self.error("coverage_output_missing", path, f"Unknown output id {oid}")
            if status in ("included", "shared") and not outputs:
                self.error("coverage_empty_output", path, "Included/shared source material must point to concrete output ids")
            if status in ("duplicate", "shared", "not_relevant"):
                self.text(item, "justification", path)
            if status == "duplicate" and not present(item.get("duplicate_of")):
                self.error("duplicate_target", path, "A duplicate decision requires another coverage item's id")
            if status != "not_relevant" and not keys:
                self.error("coverage_empty_keys", path, "A relevant coverage item requires explicit verse keys")
        for pair, block in self.blocks.items():
            decisions = pairs.get(pair, [])
            mapped = self.block_keys(block, f"sources.{pair[0]}.{pair[1]}")
            related = mapped & self.verse_keys
            if not mapped or block.get("requires_mapping") is True:
                if not decisions or any(i.get("status") != "not_relevant" or not present(i.get("justification")) for i in decisions):
                    self.error("requires_mapping", f"sources.{pair[0]}.{pair[1]}", "Unmapped material must be mapped explicitly or reviewed as not relevant with a reason")
            if related:
                covered = {k for item in decisions if isinstance(item.get("verse_keys"), list)
                           for k in item["verse_keys"] if isinstance(k, str)}
                for key in sorted(related - covered):
                    self.error("uncovered_block_verse", f"sources.{pair[0]}.{pair[1]}", f"No coverage decision for {key}")
        for cid, item in by_id.items():
            if item.get("status") != "duplicate":
                continue
            chain, current = {cid}, item
            while current.get("status") == "duplicate":
                target = current.get("duplicate_of")
                if target not in by_id:
                    self.error("duplicate_target_missing", f"coverage.{cid}", "Duplicate target does not exist")
                    break
                if target in chain:
                    self.error("duplicate_cycle", f"coverage.{cid}", "Duplicate decisions form a cycle")
                    break
                chain.add(target)
                current = by_id[target]
            else:
                if current.get("status") not in ("included", "shared"):
                    self.error("duplicate_dropped", f"coverage.{cid}", "A duplicate chain must end in included/shared output")
        for qid, sid, bid, key, path in self.quote_records:
            if not any(qid in item.get("output_ids", []) and key in item.get("verse_keys", [])
                       for item in pairs.get((sid, bid), [])
                       if isinstance(item.get("output_ids"), list) and isinstance(item.get("verse_keys"), list)):
                self.error("quote_without_coverage", path, "Quotation is not linked by coverage to its own source, block, and verse")

    def check_docx(self, path: Path):
        try:
            with zipfile.ZipFile(path) as archive:
                root = ET.fromstring(archive.read("word/document.xml"))
                paragraphs = []
                for p in root.iter(W + "p"):
                    text = "".join(t.text or "" for t in p.iter(W + "t"))
                    style = p.find(f"{W}pPr/{W}pStyle")
                    paragraphs.append((text, style.get(W + "val") if style is not None else ""))
                body = normalized("\n".join(p[0] for p in paragraphs))
                exact_body = re.sub(r"\s+", " ", unicodedata.normalize("NFC", "\n".join(p[0] for p in paragraphs))).strip()
                for origin, text in display_contract(self.study):
                    if displayed(text) not in displayed(exact_body):
                        self.error("docx_missing_text", origin, "Expected printed text is absent or changed, including its diacritics")
                expected_quran = Counter(re.sub(r"\s+", " ", unicodedata.normalize("NFC", text)).strip()
                                         for _, text in self.docx_quran_texts)
                for text, count in expected_quran.items():
                    found = exact_body.count(text)
                    if found < count:
                        origins = [origin for origin, value in self.docx_quran_texts
                                   if re.sub(r"\s+", " ", unicodedata.normalize("NFC", value)).strip() == text]
                        self.error("docx_quran_mismatch", origins[0], f"Expected at least {count} verbatim Quran occurrence(s), found {found}; diacritics must be retained: {text[:80]}")
                verses = self.study.get("verses", [])
                positions = []
                for vi, verse in enumerate(verses):
                    heading = normalized(verse.get("heading", ""))
                    found = [i for i, (text, style) in enumerate(paragraphs)
                             if style == "Heading1" and normalized(text) == heading]
                    if len(found) != 1:
                        self.error("docx_verse_heading", f"study.verses[{vi}]", "Each verse heading must occur once as Heading1")
                    else:
                        positions.append((vi, found[0]))
                if positions != sorted(positions, key=lambda p: p[1]):
                    self.error("docx_verse_order", "docx", "Verse headings are out of study order")
                for index, (vi, start) in enumerate(positions):
                    end = positions[index + 1][1] if index + 1 < len(positions) else len(paragraphs)
                    # A concluding bibliography may be Heading1, so end there too.
                    next_h1 = next((i for i in range(start + 1, end) if paragraphs[i][1] == "Heading1"), end)
                    scope = displayed('\n'.join(p[0] for p in paragraphs[start:next_h1]))
                    prefix = f'study.verses[{vi}]'
                    for origin, value in display_contract(self.study):
                        if origin.startswith(prefix + '.') and displayed(value) not in scope:
                            self.error('docx_wrong_verse_or_changed', origin, 'Printed content must appear unchanged in its own verse, not merely elsewhere in the document')
                    axes = [p for p in paragraphs[start + 1:next_h1] if p[1] == "Heading2"]
                    if len(axes) != 7:
                        self.error("docx_axis_count", f"study.verses[{vi}]", f"Expected seven Heading2 axes, found {len(axes)}")
                    numbers = []
                    for text, _ in axes:
                        probe = "".join(c for c in text if unicodedata.category(c) != "Cf")
                        match = re.match(r"^\s*([٠-٩]+)(?:\s|[.\-:؛،)–—ـ])", probe)
                        numbers.append(match.group(1) if match else None)
                    if numbers != list("١٢٣٤٥٦٧"):
                        self.error("docx_axis_order", f"study.verses[{vi}]", "Axis headings must begin with Arabic numbers ١ through ٧ in order")
                    if len(axes) == 7:
                        axis_positions = [i for i in range(start + 1, next_h1) if paragraphs[i][1] == 'Heading2'] + [next_h1]
                        fields = {'summary': 1, 'groups': 2, 'terms': 3, 'stories': 4, 'themes': 5, 'benefits': 6, 'names': 7}
                        for origin, value in display_contract(self.study):
                            if not origin.startswith(prefix + '.'):
                                continue
                            tail = origin[len(prefix) + 1:]
                            name = re.split(r'[.\[]', tail)[0]
                            axis = fields.get(name)
                            if name == 'empty_axes':
                                axis = int(tail.rsplit('.', 1)[1])
                            if axis:
                                section_text = displayed('\n'.join(p[0] for p in paragraphs[axis_positions[axis-1]+1:axis_positions[axis]]))
                                if displayed(value) not in section_text:
                                    self.error('docx_wrong_axis', origin, 'Printed field must occur unchanged under its own required axis')
                header_text = ''.join(''.join(t.text or '' for t in ET.fromstring(archive.read(n)).iter(W + 't')) for n in archive.namelist() if re.fullmatch(r'word/header[0-9]+\.xml', n))
                expected_header = self.study.get('header', self.study.get('title', '') + '  •  دِرَاسَةٌ تَفْسِيرِيَّةٌ مُقَارَنَةٌ')
                if displayed(expected_header) not in displayed(header_text):
                    self.error('docx_header_changed', 'study.header', 'Header text must retain its reviewed wording and diacritics')
                if any(True for _ in root.iter(W + "ins")) or any(True for _ in root.iter(W + "del")):
                    self.error("docx_tracked_changes", "docx", "Unresolved tracked changes remain")
                if root.find(f".//{W}sectPr") is None:
                    self.error("docx_section", "docx", "No Word page section found")
        except (OSError, zipfile.BadZipFile, KeyError, ET.ParseError) as exc:
            self.error("docx_read", "docx", str(exc))

    def run(self, docx: Path | None = None) -> dict:
        self.check_manifest()
        self.check_study()
        self.check_coverage()
        if docx:
            self.check_docx(docx)
        return {"schema_version": 1, "passed": not self.errors,
                "counts": {"sources": len(self.sources), "blocks": len(self.blocks),
                           "verses": len(self.verse_keys), "quotations": len(self.quote_records),
                           "output_ids": len(self.output_ids), "errors": len(self.errors),
                           "warnings": len(self.warnings)},
                "errors": self.errors, "warnings": self.warnings,
                "limitations": ["Coverage decisions do not prove that every distinct source meaning was inventoried.",
                                "Diacritic presence does not prove full or correct vocalization; no regex claims to certify it.",
                                "Grades, attributions, interpretations, deduplication, and Israelite classifications require scholarly review.",
                                "HTTP(S) syntax is checked, but URL accessibility and primary-source authority require browsing.",
                                "DOCX text/heading checks do not replace rendering and inspecting every actual page."]}


def load_json(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(data, dict):
        raise ValueError(f"Expected a JSON object: {path}")
    return data


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("study", "sources", "quran", "coverage", "out"):
        parser.add_argument(f"--{name}", type=Path, required=True)
    parser.add_argument("--docx", type=Path)
    args = parser.parse_args(argv)
    try:
        report = Auditor(load_json(args.study), load_json(args.sources),
                         load_json(args.quran), load_json(args.coverage)).run(args.docx)
    except (OSError, ValueError, TypeError, KeyError) as exc:
        report = {"schema_version": 1, "passed": False,
                  "errors": [{"code": "invalid_input", "path": "input", "message": str(exc)}],
                  "warnings": [], "limitations": ["Invalid input prevented a complete audit."]}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"passed": report["passed"], "errors": len(report["errors"]),
                      "warnings": len(report["warnings"]), "out": str(args.out.resolve())}, ensure_ascii=False))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
