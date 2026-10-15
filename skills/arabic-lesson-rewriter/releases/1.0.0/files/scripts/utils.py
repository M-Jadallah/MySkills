"""Shared helpers for the arabic-lesson-rewriter skill scripts.

Only stdlib + the two local modules (lesson_docx, arabic_text) - no coupling
to anything else, so every script stays runnable from any working directory
(python adds the script's own folder to sys.path automatically).
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from arabic_text import normalize_arabic_text


def load_json(path: str | Path) -> Any:
    """Load JSON tolerating a UTF-8 BOM (common in Windows-authored files)."""
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def deep_normalize(data: Any) -> Any:
    """Apply normalize_arabic_text (salawat -> tanween -> digits) to every string,
    recursively. Idempotent, so running it on already-clean text is a no-op."""
    if isinstance(data, str):
        return normalize_arabic_text(data)
    if isinstance(data, list):
        return [deep_normalize(item) for item in data]
    if isinstance(data, dict):
        return {key: deep_normalize(value) for key, value in data.items()}
    return data


def safe_filename(text: str, fallback: str = "lesson") -> str:
    """Filesystem-safe, Arabic-preserving filename derived from the lesson title."""
    text = (text or "").strip()
    text = re.sub(r"[\\/:*?\"<>|\n\r\t]+", " ", text)
    text = re.sub(r"\s+", "_", text.strip())
    text = re.sub(r"[^\w؀-ۿݐ-ݿࢠ-ࣿ\-_.]+", "", text)
    return (text[:80] or fallback).strip("._-") or fallback
