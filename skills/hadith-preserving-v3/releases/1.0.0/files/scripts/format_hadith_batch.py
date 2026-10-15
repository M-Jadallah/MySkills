#!/usr/bin/env python3
"""Parallel multi-book orchestrator for hadith TXT files.

Each numbered TXT file is processed in an isolated worker. The main process
validates every worker result, retries safe text-preservation repairs, merges
all books in filename-number order, and performs one global pagination pass.
"""
from __future__ import annotations

import argparse
import concurrent.futures
import importlib.util
import json
import re
import tempfile
import traceback
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Sequence

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("format_hadith", ROOT / "scripts" / "format_hadith.py")
core = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = core
assert SPEC.loader is not None
SPEC.loader.exec_module(core)

NUMBERED_FILE_RE = re.compile(r"^\s*(\d+)\s*(?:[-–—_. ]+)\s*(.+?)\s*\.txt$", re.IGNORECASE)


def discover_books(input_dir: Path) -> list[tuple[int, str, Path]]:
    books: list[tuple[int, str, Path]] = []
    invalid: list[str] = []
    for path in input_dir.iterdir():
        if not path.is_file() or path.suffix.lower() != ".txt":
            continue
        match = NUMBERED_FILE_RE.match(path.name)
        if not match:
            invalid.append(path.name)
            continue
        books.append((int(match.group(1)), match.group(2).strip(), path))
    if invalid:
        raise ValueError("TXT filenames must start with an ordering number: " + ", ".join(sorted(invalid)))
    if not books:
        raise ValueError(f"No numbered TXT files were found in {input_dir}")
    books.sort(key=lambda item: (item[0], item[2].name))
    duplicates = [number for number in {item[0] for item in books} if sum(book[0] == number for book in books) > 1]
    if duplicates:
        raise ValueError(f"Duplicate book order numbers are not allowed: {sorted(duplicates)}")
    return books


def process_book_worker(payload: dict) -> dict:
    path = Path(payload["path"])
    config = payload["config"]
    max_attempts = int(payload["max_attempts"])
    original = core.read_utf8(path)
    cycles: list[dict] = []
    last_error: Exception | None = None

    # Multiple self-repair cycles. Each cycle restarts from the original source;
    # no cycle is allowed to modify Arabic letters or diacritics.
    for cycle in range(1, 4):
        try:
            cleaned, stats, units, repair_log = core.process_source_with_repairs(
                original,
                config,
                source_file=path.name,
                max_attempts=max_attempts + cycle - 1,
            )
            core.audit_unit_preservation(cleaned, units)
            semantic_path = Path(payload["semantic_map"]) if payload.get("semantic_map") else None
            semantic_info = core.apply_semantic_map(units, semantic_path)
            cycles.append({"cycle": cycle, "status": "PASS", "repair_log": repair_log, "semantic": semantic_info})
            return {
                "status": "PASS",
                "path": str(path),
                "filename": path.name,
                "order": int(payload["order"]),
                "book_name": payload["book_name"],
                "original_sha256": core.sha256_text(original),
                "cleaned": cleaned,
                "cleaned_sha256": core.sha256_text(core.compact_chars(cleaned)),
                "stats": asdict(stats),
                "repair_cycles": cycles,
                "semantic_processing": semantic_info,
                "units": [asdict(unit) for unit in units],
            }
        except Exception as exc:
            last_error = exc
            cycles.append({
                "cycle": cycle,
                "status": "RETRY",
                "error": str(exc),
                "traceback": traceback.format_exc(limit=6),
            })
    return {
        "status": "FAILED",
        "path": str(path),
        "filename": path.name,
        "order": int(payload["order"]),
        "book_name": payload["book_name"],
        "repair_cycles": cycles,
        "error": str(last_error),
    }


def compact_worker_summary(result: dict) -> dict:
    summary = {key: value for key, value in result.items() if key not in {"cleaned", "units"}}
    units = result.get("units", [])
    if units:
        summary["unit_summary"] = {
            "total": len(units),
            "titles": sum(unit.get("kind") == "title" for unit in units),
            "hadiths": sum(unit.get("kind") == "hadith" for unit in units),
            "body_blocks": sum(unit.get("kind") == "body" for unit in units),
            "hadith_numbers": [unit.get("hadith_number") for unit in units if unit.get("kind") == "hadith"],
        }
    return summary


def write_intermediate(result: dict, output_dir: Path) -> None:
    book_dir = output_dir / f"{result['order']:03d}-{result['book_name']}"
    book_dir.mkdir(parents=True, exist_ok=True)
    (book_dir / "worker-result.json").write_text(
        json.dumps(compact_worker_summary(result), ensure_ascii=False, indent=2), encoding="utf-8"
    )
    if result["status"] == "PASS":
        (book_dir / "cleaned.txt").write_text(result["cleaned"].strip() + "\n", encoding="utf-8")
        (book_dir / "units.json").write_text(json.dumps(result["units"], ensure_ascii=False, indent=2), encoding="utf-8")


def merge_units(results: Sequence[dict]) -> list:
    merged = []
    for result in sorted(results, key=lambda item: item["order"]):
        for unit_data in result["units"]:
            unit = core.Unit(**unit_data)
            unit.index = len(merged)
            merged.append(unit)
    return merged


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Format and merge multiple numbered hadith TXT books into one DOCX.")
    parser.add_argument("input_dir", type=Path)
    parser.add_argument("output_docx", type=Path)
    parser.add_argument("--config", type=Path, default=ROOT / "config" / "default.json")
    parser.add_argument("--audit-json", type=Path)
    parser.add_argument("--clean-txt", type=Path)
    parser.add_argument("--workdir", type=Path)
    parser.add_argument("--intermediate-dir", type=Path)
    parser.add_argument("--jobs", type=int, default=0, help="0 uses one worker per book up to the executor default.")
    parser.add_argument("--max-repair-attempts", type=int, default=4)
    parser.add_argument("--semantic-dir", type=Path, help="Directory of AI semantic maps named <TXT stem>.semantic.json")
    parser.add_argument("--skip-pagination", action="store_true")
    args = parser.parse_args(argv)

    config = json.loads(args.config.read_text(encoding="utf-8"))
    books = discover_books(args.input_dir)
    payloads = []
    for order, name, path in books:
        semantic_map = None
        if args.semantic_dir:
            candidate = args.semantic_dir / f"{path.stem}.semantic.json"
            if candidate.exists():
                semantic_map = str(candidate)
        else:
            candidate = path.with_name(f"{path.stem}.semantic.json")
            if candidate.exists():
                semantic_map = str(candidate)
        payloads.append({
            "order": order,
            "book_name": name,
            "path": str(path),
            "config": config,
            "max_attempts": args.max_repair_attempts,
            "semantic_map": semantic_map,
        })

    max_workers = args.jobs if args.jobs > 0 else None
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        results = list(executor.map(process_book_worker, payloads))
    results.sort(key=lambda item: item["order"])

    temporary = None
    if args.workdir:
        args.workdir.mkdir(parents=True, exist_ok=True)
        workdir = args.workdir
    else:
        temporary = tempfile.TemporaryDirectory(prefix="hadith_batch_")
        workdir = Path(temporary.name)
    intermediate_dir = args.intermediate_dir or workdir / "book_workers"
    intermediate_dir.mkdir(parents=True, exist_ok=True)
    for result in results:
        write_intermediate(result, intermediate_dir)

    failures = [result for result in results if result["status"] != "PASS"]
    if failures:
        failure_report = {
            "status": "FAILED_AFTER_AUTOMATIC_REPAIR",
            "message": "No incomplete Word file was created. The listed raw sources need human clarification because safe retries could not prove preservation.",
            "failures": failures,
        }
        report_path = (args.audit_json or args.output_docx.with_suffix(".audit.json"))
        report_path.write_text(json.dumps(failure_report, ensure_ascii=False, indent=2), encoding="utf-8")
        raise RuntimeError(f"Automatic repair could not safely resolve: {[item['filename'] for item in failures]}")

    units = merge_units(results)
    if not units:
        raise RuntimeError("Workers succeeded but produced no units.")
    layout = core.format_units(units, config, args.output_docx, workdir / "final", skip_pagination=args.skip_pagination)

    clean_path = args.clean_txt or args.output_docx.with_suffix(".clean.txt")
    core.write_clean_text(units, clean_path)
    combined_clean = "\n".join(unit.text for unit in units)
    audit = {
        "skill": config["skill_name"],
        "version": config["version"],
        "mode": "multi-book-parallel",
        "input_directory": str(args.input_dir),
        "output": str(args.output_docx),
        "clean_text": str(clean_path),
        "preservation_check": "PASS",
        "semantic_bold_check": core.verify_semantic_bold_docx(args.output_docx, units),
        "book_order": [
            {"order": result["order"], "filename": result["filename"], "book_name": result["book_name"]}
            for result in results
        ],
        "workers": [compact_worker_summary(result) for result in results],
        "merged": {
            "books": len(results),
            "units": len(units),
            "hadiths": sum(unit.kind == "hadith" for unit in units),
            "cleaned_non_whitespace_sha256": core.sha256_text(core.compact_chars(combined_clean)),
        },
        "layout": asdict(layout),
        "rules": {
            "parallel_isolated_worker_per_file": True,
            "global_final_pagination": True,
            "part_pages": config["part_pages"],
            "last_part_may_be_shorter": True,
            "no_incomplete_silent_output": True,
            "automatic_safe_repair_cycles": 3,
            "ai_semantic_exact_anchor_maps": True,
            "matn_and_meanings_always_bold": True,
            "arabic_bold_flags": ["w:b", "w:bCs"],
        },
    }
    audit_path = args.audit_json or args.output_docx.with_suffix(".audit.json")
    audit_path.write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({
        "docx": str(args.output_docx),
        "clean_txt": str(clean_path),
        "audit": str(audit_path),
        "books": len(results),
    }, ensure_ascii=False))
    if temporary is not None:
        temporary.cleanup()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
