"""Discover transcript files and prepare the workspace folders.

Creates lessons_input/ and lessons_output/ under the target directory
(default: current working directory) and lists the .txt transcripts ready
for processing - one JSON line of truth for planning subagent dispatch.

Usage:
    python scripts/orchestrator.py [directory-or-file]
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from utils import safe_filename


def main() -> int:
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else Path.cwd()

    if target.is_file():
        input_dir = target.parent
        output_dir = input_dir / "lessons_output"
    else:
        input_dir = target / "lessons_input"
        output_dir = target / "lessons_output"

    output_dir.mkdir(parents=True, exist_ok=True)
    if not input_dir.exists():
        input_dir.mkdir(parents=True, exist_ok=True)

    if target.is_file():
        files = [str(target.resolve())]
    else:
        files = sorted(str(p.resolve()) for p in input_dir.glob("*.txt"))

    report = {
        "input_dir": str(input_dir.resolve()),
        "output_dir": str(output_dir.resolve()),
        "files": files,
        "suggested_outputs": [safe_filename(Path(f).stem) + ".docx" for f in files],
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
