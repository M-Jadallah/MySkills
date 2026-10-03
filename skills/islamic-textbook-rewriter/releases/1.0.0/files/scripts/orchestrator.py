"""Discover textbook transcript inputs without creating empty input folders."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from utils import safe_filename

SUPPORTED = {".txt", ".pdf"}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("target", nargs="?", default=".")
    args = parser.parse_args()
    target = Path(args.target).resolve()
    if not target.exists():
        print(json.dumps({"ok": False, "error": "المسار غير موجود"}, ensure_ascii=False))
        return 1
    if target.is_file():
        if target.suffix.lower() not in SUPPORTED:
            print(json.dumps({"ok": False, "error": "المدخل المدعوم TXT أو PDF"}, ensure_ascii=False))
            return 1
        inputs, root = [target], target.parent
    else:
        root = target
        folder = root / "lessons_input" if (root / "lessons_input").is_dir() else root
        inputs = sorted((p for p in folder.iterdir() if p.is_file() and p.suffix.lower() in SUPPORTED), key=lambda p: p.name)
    output = root / "lessons_output"
    print(json.dumps({"ok": bool(inputs), "files": [str(p) for p in inputs], "inputs": [{"path": str(p), "format": p.suffix.lower()[1:], "reading_mode": "page_images_and_text" if p.suffix.lower() == ".pdf" else "text"} for p in inputs], "output_dir": str(output), "suggested_outputs": [str(output / (safe_filename(p.stem) + ".docx")) for p in inputs]}, ensure_ascii=False, indent=2))
    return 0 if inputs else 1


if __name__ == "__main__":
    raise SystemExit(main())
