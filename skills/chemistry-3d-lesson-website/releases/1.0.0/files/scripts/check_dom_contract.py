#!/usr/bin/env python3
"""Validate the minimum testability and RTL DOM contract in standalone HTML."""

from __future__ import annotations

import argparse
from html.parser import HTMLParser
from pathlib import Path

REQUIRED_ATTRIBUTES = {
    "data-lesson-section": 1,
    "data-science-sim": 1,
    "data-simulation-canvas": 1,
    "data-control-id": 1,
    "data-verification-card": 1,
    "data-final-assessment": 1,
}


class ContractParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.counts = {key: 0 for key in REQUIRED_ATTRIBUTES}
        self.html_dir = None
        self.controls: list[dict[str, str]] = []
        self.labels_for: set[str] = set()

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = {key: value or "" for key, value in attrs}
        if tag == "html":
            self.html_dir = attributes.get("dir")
        for key in self.counts:
            if key in attributes:
                self.counts[key] += 1
        if tag == "label" and attributes.get("for"):
            self.labels_for.add(attributes["for"])
        if tag in {"input", "select", "textarea"}:
            self.controls.append(attributes)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--html", required=True)
    args = parser.parse_args()

    path = Path(args.html)
    text = path.read_text(encoding="utf-8")
    checker = ContractParser()
    checker.feed(text)

    errors = []
    if checker.html_dir != "rtl":
        errors.append("root <html> element must use dir=\"rtl\"")
    for attribute, minimum in REQUIRED_ATTRIBUTES.items():
        if checker.counts[attribute] < minimum:
            errors.append(f"missing required DOM hook: {attribute}")

    for index, control in enumerate(checker.controls):
        control_id = control.get("id", "")
        has_name = bool(
            control.get("aria-label")
            or control.get("aria-labelledby")
            or control.get("title")
            or (control_id and control_id in checker.labels_for)
        )
        if not has_name and control.get("type") != "hidden":
            errors.append(f"control[{index}] has no accessible label: {control}")

    if "<!-- FOOTER_LOCK_START -->" not in text or "<!-- FOOTER_LOCK_END -->" not in text:
        errors.append("footer lock markers are missing")

    if errors:
        print("DOM contract validation failed:")
        for error in errors:
            print(f"- {error}")
        return 1

    print("DOM contract validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
