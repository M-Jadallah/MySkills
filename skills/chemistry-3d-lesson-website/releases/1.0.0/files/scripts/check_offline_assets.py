#!/usr/bin/env python3
"""Audit HTML/CSS/JS for remote URLs and missing local assets."""

from __future__ import annotations

import argparse
import re
from pathlib import Path
from urllib.parse import unquote, urlsplit

TEXT_EXTENSIONS = {".html", ".htm", ".css", ".js", ".mjs", ".cjs", ".ts", ".tsx", ".jsx", ".svg"}
REMOTE_RE = re.compile(r"(?P<url>(?:https?:)?//[^\s'\"<>\)]+)", re.IGNORECASE)
ATTR_RE = re.compile(r"(?:src|href|poster)\s*=\s*['\"](?P<url>[^'\"]+)['\"]", re.IGNORECASE)
CSS_URL_RE = re.compile(r"url\(\s*['\"]?(?P<url>[^'\")]+)", re.IGNORECASE)


def iter_text_files(path: Path):
    if path.is_file():
        yield path
    else:
        yield from (item for item in path.rglob("*") if item.is_file() and item.suffix.lower() in TEXT_EXTENSIONS)


def is_ignored(url: str) -> bool:
    normalized = url.strip().lower()
    return (
        not normalized
        or normalized.startswith(("#", "data:", "blob:", "mailto:", "tel:", "javascript:"))
        or "{{" in normalized
        or "${" in normalized
    )


def local_target(source_file: Path, url: str) -> Path | None:
    if is_ignored(url):
        return None
    parsed = urlsplit(url)
    if parsed.scheme or parsed.netloc:
        return None
    clean = unquote(parsed.path)
    if not clean or clean.startswith("/"):
        return None
    return (source_file.parent / clean).resolve()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--path", required=True)
    parser.add_argument("--fail-on-remote", action="store_true")
    parser.add_argument("--fail-on-missing", action="store_true")
    args = parser.parse_args()

    root = Path(args.path).resolve()
    remote = []
    missing = []
    for file in iter_text_files(root):
        try:
            text = file.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for match in REMOTE_RE.finditer(text):
            remote.append((file, match.group("url")))
        urls = [match.group("url") for match in ATTR_RE.finditer(text)]
        urls.extend(match.group("url") for match in CSS_URL_RE.finditer(text))
        for url in urls:
            target = local_target(file, url)
            if target is not None and not target.exists():
                missing.append((file, url, target))

    if remote:
        print("Remote URL references:")
        for file, url in remote:
            print(f"- {file}: {url}")
    if missing:
        print("Missing local assets:")
        for file, url, target in missing:
            print(f"- {file}: {url} -> {target}")
    if not remote and not missing:
        print("Offline asset audit passed: no remote URLs or missing local assets found.")

    failed = (args.fail_on_remote and bool(remote)) or (args.fail_on_missing and bool(missing))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
