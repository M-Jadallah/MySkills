#!/usr/bin/env python3
"""Preserve tafsir TXT sources and locate explicitly numbered verse blocks.

This is an inventory helper, not an interpreter. It never strips isnads,
footnotes, headings, punctuation, diacritics, or repeated source material.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import unicodedata
from pathlib import Path

DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")
NUMBERED = re.compile(
    r"^(?:الآية|الآيات|آية|آيات)\s*(?:رقم\s*)?[:：]?\s*"
    r"[\[(]?\s*(\d{1,3})(?:\s*(?:[-–—−]|إلى)\s*(\d{1,3}))?\s*[\])]?"
    r"(?:\s*\(نطاق المصدر\))?[.:：]?\s*$"
)
HEADING_CANDIDATE = re.compile(r"^(?:الآية|الآيات|آية|آيات)(?:\s|[:：]|$)")


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def detection_text(text: str) -> str:
    """A detection-only view; never written back over the original text."""
    text = unicodedata.normalize("NFC", text).translate(DIGITS)
    text = "".join(c for c in text if not unicodedata.category(c).startswith("M")
                   and c != "ـ" and unicodedata.category(c) != "Cf")
    return re.sub(r"^[\s#*]+|[\s#*]+$", "", text)


def decode_source(data: bytes, encoding: str | None = None) -> tuple[str, str]:
    if encoding:
        return data.decode(encoding, errors="strict"), encoding
    # UTF-32 BOMs must be tested before their UTF-16 prefix.
    for bom, codec in ((b"\xff\xfe\x00\x00", "utf-32"),
                       (b"\x00\x00\xfe\xff", "utf-32"),
                       (b"\xff\xfe", "utf-16"), (b"\xfe\xff", "utf-16"),
                       (b"\xef\xbb\xbf", "utf-8-sig")):
        if data.startswith(bom):
            return data.decode(codec, errors="strict"), codec
    # Do not silently guess a legacy encoding or replace unreadable characters.
    return data.decode("utf-8", errors="strict"), "utf-8"


def make_block(raw: str, index: int, start: int, end: int, label: str,
               verses: list[int], surah: int | None, header_end: int | None = None,
               reason: str | None = None) -> dict:
    text = raw[start:end]
    block = {"id": f"b{index:03d}", "label": label, "verses": verses,
             "verse_keys": [f"{surah}:{v}" for v in verses] if surah else [],
             "start": start, "end": end, "text": text,
             "sha256": digest(text.encode("utf-8")),
             "requires_mapping": not bool(verses)}
    if header_end is not None:
        block["header_end"] = header_end
        block["content_sha256"] = digest(raw[header_end:end].encode("utf-8"))
    if reason:
        block["mapping_reason"] = reason
    return block


def split_blocks(raw: str, surah: int | None = None) -> list[dict]:
    boundaries = []
    offset = 0
    for line in raw.splitlines(keepends=True):
        probe = detection_text(line)
        if HEADING_CANDIDATE.match(probe) and len(probe) <= 160:
            match = NUMBERED.fullmatch(probe)
            verses, reason = [], None
            if match:
                first = int(match.group(1))
                last = int(match.group(2) or first)
                if 1 <= first <= last <= 286:
                    verses = list(range(first, last + 1))
                else:
                    reason = "invalid_or_reversed_verse_range"
            else:
                reason = "unrecognized_verse_heading"
            boundaries.append((offset, offset + len(line), line.rstrip("\r\n"), verses, reason))
        offset += len(line)
    if not boundaries:
        return [make_block(raw, 1, 0, len(raw), "Unmapped source", [], surah,
                           reason="no_explicit_numbered_verse_heading")]
    blocks = []
    if boundaries[0][0] > 0:
        blocks.append(make_block(raw, 0, 0, boundaries[0][0], "Unmapped preamble", [], surah,
                                 reason="preamble_requires_review"))
    for index, (start, header_end, label, verses, reason) in enumerate(boundaries, 1):
        end = boundaries[index][0] if index < len(boundaries) else len(raw)
        blocks.append(make_block(raw, index, start, end, label, verses, surah,
                                 header_end=header_end, reason=reason))
    return blocks


def extract_metadata(raw: str, filename: str) -> tuple[str, str | None]:
    # Metadata is recorded as printed; a name is never guessed to identify an author.
    name, author = filename, None
    for line in raw.splitlines()[:100]:
        match = re.match(r"^\s*التفسير\s*[:：]\s*(.+?)\s*$", line)
        if match and name == filename:
            name = match.group(1)
        match = re.match(r"^\s*المؤلف\s*[:：]\s*(.+?)\s*$", line)
        if match and author is None:
            author = match.group(1)
    return name, author


def ingest(paths: list[Path], surah: int | None = None,
           encoding: str | None = None) -> dict:
    sources, by_file, by_block, by_content = [], {}, {}, {}
    resolved = set()
    for path in paths:
        path = path.resolve(strict=True)
        if path in resolved:
            raise ValueError(f"The same path was supplied twice: {path}")
        resolved.add(path)
        if not path.is_file():
            raise ValueError(f"Not a regular file: {path}")
        data = path.read_bytes()
        raw, used_encoding = decode_source(data, encoding)
        name, author = extract_metadata(raw, path.stem)
        sid = f"s{len(sources) + 1:02d}"
        source = {"id": sid, "path": str(path), "name": name, "author": author,
                  "encoding": used_encoding, "byte_length": len(data),
                  "raw_text": raw, "sha256": digest(data),
                  "raw_text_sha256": digest(raw.encode("utf-8")),
                  "blocks": split_blocks(raw, surah)}
        sources.append(source)
        by_file.setdefault(source["sha256"], []).append(sid)
        for block in source["blocks"]:
            by_block.setdefault(block["sha256"], []).append({"source_id": sid, "block_id": block["id"]})
            if block.get("content_sha256"):
                by_content.setdefault(block["content_sha256"], []).append({"source_id": sid, "block_id": block["id"]})
    return {"schema_version": 1, "offset_unit": "unicode_codepoint",
            "span_convention": "zero_based_half_open",
            "surah_number": surah, "sources": sources,
            "exact_duplicate_files": [ids for ids in by_file.values() if len(ids) > 1],
            "exact_duplicate_blocks": [ids for ids in by_block.values() if len(ids) > 1],
            "exact_duplicate_content": [ids for ids in by_content.values() if len(ids) > 1],
            "notes": ["Duplicate flags are observations, not permission to merge sources or author identities.",
                      "All unmapped preambles and headings require an explicit review decision.",
                      "Raw content is preserved; normalization is used only to detect headings."]}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    inputs = parser.add_mutually_exclusive_group(required=True)
    inputs.add_argument("--inputs", nargs="+", type=Path)
    inputs.add_argument("--source-dir", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--surah", type=int, help="Explicit surah number; never inferred from a filename")
    parser.add_argument("--encoding", help="Explicit legacy encoding, if UTF/BOM detection is insufficient")
    args = parser.parse_args(argv)
    try:
        if args.surah is not None and not 1 <= args.surah <= 114:
            raise ValueError("--surah must be in 1..114")
        paths = args.inputs or sorted((p for p in args.source_dir.iterdir()
                                       if p.is_file() and p.suffix.lower() == ".txt"),
                                      key=lambda p: (p.name.casefold(), p.name))
        if not paths:
            raise ValueError("No TXT sources were supplied or found")
        result = ingest(paths, args.surah, args.encoding)
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps({"sources": len(result["sources"]),
                          "blocks": sum(len(s["blocks"]) for s in result["sources"]),
                          "requires_mapping": sum(b["requires_mapping"] for s in result["sources"] for b in s["blocks"]),
                          "out": str(args.out.resolve())}, ensure_ascii=False))
        return 0
    except (OSError, UnicodeError, ValueError) as exc:
        print(f"Ingestion failed: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
