#!/usr/bin/env python3
"""Inventory lesson, reference project, standalone HTML, and brand assets."""

from __future__ import annotations

import argparse
import mimetypes
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from common import relpath_or_absolute, sha256_file, write_json


def describe_path(path: Path, role: str, base: Path) -> dict[str, Any]:
    if not path.exists():
        return {"role": role, "path": str(path), "exists": False}

    if path.is_file():
        return {
            "role": role,
            "path": relpath_or_absolute(path, base),
            "exists": True,
            "kind": "file",
            "size_bytes": path.stat().st_size,
            "extension": path.suffix.lower(),
            "mime_type": mimetypes.guess_type(path.name)[0],
            "sha256": sha256_file(path),
        }

    files = []
    total_size = 0
    for item in sorted(p for p in path.rglob("*") if p.is_file()):
        size = item.stat().st_size
        total_size += size
        files.append(
            {
                "path": str(item.relative_to(path)),
                "size_bytes": size,
                "extension": item.suffix.lower(),
                "sha256": sha256_file(item),
            }
        )
    return {
        "role": role,
        "path": relpath_or_absolute(path, base),
        "exists": True,
        "kind": "directory",
        "file_count": len(files),
        "size_bytes": total_size,
        "files": files,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lesson", required=True)
    parser.add_argument("--reference-project")
    parser.add_argument("--reference-html")
    parser.add_argument("--brand-assets")
    parser.add_argument("--output", required=True, help="Output prefix or directory")
    args = parser.parse_args()

    cwd = Path.cwd()
    entries = [describe_path(Path(args.lesson), "lesson", cwd)]
    for value, role in [
        (args.reference_project, "reference-project"),
        (args.reference_html, "reference-html"),
        (args.brand_assets, "brand-assets"),
    ]:
        if value:
            entries.append(describe_path(Path(value), role, cwd))

    inventory = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "entries": entries,
    }

    output = Path(args.output)
    if output.suffix:
        json_path = output.with_suffix(".json")
        md_path = output.with_suffix(".md")
    else:
        output.mkdir(parents=True, exist_ok=True)
        json_path = output / "input-inventory.json"
        md_path = output / "input-inventory.md"

    write_json(json_path, inventory)

    lines = ["# Input Inventory", "", f"Generated: {inventory['generated_at']}", ""]
    for entry in entries:
        lines.append(f"## {entry['role']}")
        lines.append("")
        lines.append(f"- Path: `{entry['path']}`")
        lines.append(f"- Exists: `{entry['exists']}`")
        if entry.get("exists"):
            lines.append(f"- Kind: `{entry['kind']}`")
            lines.append(f"- Size: `{entry['size_bytes']}` bytes")
            if entry["kind"] == "file":
                lines.append(f"- SHA-256: `{entry['sha256']}`")
            else:
                lines.append(f"- Files: `{entry['file_count']}`")
        lines.append("")
    md_path.write_text("\n".join(lines), encoding="utf-8")

    missing = [entry for entry in entries if not entry["exists"]]
    print(f"Wrote {json_path} and {md_path}")
    return 1 if missing else 0


if __name__ == "__main__":
    raise SystemExit(main())
