#!/usr/bin/env python3
"""Create a deterministic release ZIP after validating required artifacts."""

from __future__ import annotations

import argparse
import json
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from common import load_json, sha256_file

EXCLUDED_NAMES = {"node_modules", ".git", ".idea", ".vscode", "__pycache__", ".pytest_cache"}
EXCLUDED_SUFFIXES = {".pyc", ".pyo", ".log.tmp"}


def should_include(path: Path, root: Path) -> bool:
    rel = path.relative_to(root)
    if any(part in EXCLUDED_NAMES for part in rel.parts):
        return False
    if path.suffix.lower() in EXCLUDED_SUFFIXES:
        return False
    return path.is_file()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--config", required=True)
    args = parser.parse_args()

    root = Path(args.project_root).resolve()
    output = Path(args.output).resolve()
    config = load_json(Path(args.config).resolve())
    required = config.get("quality_gate", {}).get("required_files", [])
    missing = [item for item in required if not (root / item).exists()]
    if missing:
        print("Cannot package release; required files are missing:")
        for item in missing:
            print(f"- {item}")
        return 1

    files = sorted(path for path in root.rglob("*") if should_include(path, root) and path.resolve() != output)
    manifest = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "project_root": str(root),
        "files": [
            {
                "path": str(path.relative_to(root)).replace("\\", "/"),
                "size_bytes": path.stat().st_size,
                "sha256": sha256_file(path),
            }
            for path in files
        ],
    }

    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in files:
            arcname = str(path.relative_to(root)).replace("\\", "/")
            info = zipfile.ZipInfo(arcname)
            info.date_time = (2020, 1, 1, 0, 0, 0)
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, path.read_bytes())
        manifest_info = zipfile.ZipInfo("release-manifest.json")
        manifest_info.date_time = (2020, 1, 1, 0, 0, 0)
        manifest_info.compress_type = zipfile.ZIP_DEFLATED
        archive.writestr(manifest_info, json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")

    print(f"Created release archive: {output}")
    print(f"Included files: {len(files)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
