"""Self-contained JSON and field-aware normalization helpers."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from arabic_text import normalize_prose

DISPLAY_KEYS = {"title", "subtitle", "heading", "text", "items", "headers", "rows", "label", "children", "citation", "note", "takeaway"}
OPAQUE_KEYS = {"sources", "verification", "source_id", "map_policy", "map_omission_reason", "kind", "type", "presentation"}


def load_json(path: str | Path) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def normalize_lesson(data: Any, field: str = "") -> Any:
    if field in OPAQUE_KEYS:
        return data
    if isinstance(data, str):
        return normalize_prose(data) if field in DISPLAY_KEYS else data
    if isinstance(data, list):
        return [normalize_lesson(item, field) for item in data]
    if isinstance(data, dict):
        is_evidence = data.get("type") == "evidence"
        return {
            key: value if is_evidence and key == "text" else normalize_lesson(value, key)
            for key, value in data.items()
        }
    return data


def safe_filename(text: str, fallback: str = "lesson") -> str:
    text = re.sub(r'[\\/:*?"<>|\r\n\t]+', " ", text.strip())
    text = re.sub(r"\s+", "_", text).strip("._-")[:90]
    return text or fallback
