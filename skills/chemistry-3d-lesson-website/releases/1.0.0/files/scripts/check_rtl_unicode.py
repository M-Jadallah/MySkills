#!/usr/bin/env python3
"""Scan source files for risky bidi controls and malformed Unicode characters."""

from __future__ import annotations

import argparse
from pathlib import Path

TEXT_EXTENSIONS = {
    ".html", ".htm", ".css", ".js", ".mjs", ".cjs", ".ts", ".tsx", ".jsx",
    ".json", ".md", ".txt", ".svg", ".xml", ".yaml", ".yml",
}

RISKY = {
    "\u202a": "LEFT-TO-RIGHT EMBEDDING",
    "\u202b": "RIGHT-TO-LEFT EMBEDDING",
    "\u202c": "POP DIRECTIONAL FORMATTING",
    "\u202d": "LEFT-TO-RIGHT OVERRIDE",
    "\u202e": "RIGHT-TO-LEFT OVERRIDE",
    "\u2066": "LEFT-TO-RIGHT ISOLATE",
    "\u2067": "RIGHT-TO-LEFT ISOLATE",
    "\u2068": "FIRST STRONG ISOLATE",
    "\u2069": "POP DIRECTIONAL ISOLATE",
    "\ufffd": "REPLACEMENT CHARACTER",
}


def iter_text_files(path: Path):
    if path.is_file():
        if path.suffix.lower() in TEXT_EXTENSIONS:
            yield path
        return
    for item in path.rglob("*"):
        if item.is_file() and item.suffix.lower() in TEXT_EXTENSIONS:
            yield item


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--path", required=True)
    parser.add_argument("--fail-on-found", action="store_true")
    args = parser.parse_args()

    root = Path(args.path)
    findings = []
    for file in iter_text_files(root):
        try:
            text = file.read_text(encoding="utf-8")
        except UnicodeDecodeError as exc:
            findings.append((file, 0, "INVALID UTF-8", str(exc)))
            continue
        for line_number, line in enumerate(text.splitlines(), 1):
            for char, name in RISKY.items():
                if char in line:
                    findings.append((file, line_number, name, f"U+{ord(char):04X}"))

    if findings:
        print("Risky RTL/Unicode findings:")
        for file, line_number, name, code in findings:
            print(f"- {file}:{line_number}: {name} ({code})")
        return 1 if args.fail_on_found else 0

    print("No risky bidi controls or replacement characters found.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
