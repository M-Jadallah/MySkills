#!/usr/bin/env python3
"""Create or verify a normalized fingerprint for the locked approved footer."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

START = "<!-- FOOTER_LOCK_START -->"
END = "<!-- FOOTER_LOCK_END -->"


def extract(html: str) -> str:
    start = html.find(START)
    end = html.find(END)
    if start < 0 or end < 0 or end <= start:
        raise ValueError("Footer lock markers were not found or are out of order")
    return html[start + len(START):end]


def normalize(fragment: str) -> str:
    fragment = re.sub(r"<!--(?!\s*FOOTER_LOCK_).*?-->", "", fragment, flags=re.DOTALL)
    fragment = re.sub(r">\s+<", "><", fragment)
    fragment = re.sub(r"\s+", " ", fragment)
    return fragment.strip()


def digest(fragment: str) -> str:
    return hashlib.sha256(normalize(fragment).encode("utf-8")).hexdigest()


def fingerprint(args: argparse.Namespace) -> int:
    html_path = Path(args.html)
    fragment = extract(html_path.read_text(encoding="utf-8"))
    data = {
        "algorithm": "sha256",
        "normalization": "remove non-lock comments; collapse inter-tag and general whitespace",
        "fingerprint": digest(fragment),
        "source": str(html_path),
    }
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote footer fingerprint: {output}")
    return 0


def verify(args: argparse.Namespace) -> int:
    lock = json.loads(Path(args.lock).read_text(encoding="utf-8"))
    html = Path(args.html).read_text(encoding="utf-8")
    actual = digest(extract(html))
    expected = lock.get("fingerprint")
    if actual != expected:
        print("Footer lock verification failed.")
        print(f"Expected: {expected}")
        print(f"Actual:   {actual}")
        return 1
    print("Footer lock verification passed.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    fp = sub.add_parser("fingerprint")
    fp.add_argument("--html", required=True)
    fp.add_argument("--output", required=True)
    fp.set_defaults(func=fingerprint)

    check = sub.add_parser("verify")
    check.add_argument("--html", required=True)
    check.add_argument("--lock", required=True)
    check.set_defaults(func=verify)

    args = parser.parse_args()
    try:
        return args.func(args)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"Footer lock error: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
