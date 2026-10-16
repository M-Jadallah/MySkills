"""Snapshot lesson sources and prepare independent analysis jobs; no model calls.

Run directories are single-use. Every character offset used downstream refers to
the normalized UTF-8/LF snapshot, while the original bytes remain available.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import sys
import uuid


def decode_source(raw: bytes) -> str:
    """Decode supported transcript encodings strictly, without discarding bytes."""
    if raw.startswith((b"\xff\xfe", b"\xfe\xff")):
        encodings = ("utf-16",)
    elif raw.startswith(b"\xef\xbb\xbf"):
        encodings = ("utf-8-sig",)
    else:
        encodings = ("utf-8", "cp1256")
    for encoding in encodings:
        try:
            text = raw.decode(encoding, errors="strict")
        except UnicodeError:
            continue
        if "\x00" in text or "\ufffd" in text:
            continue
        if any(ord(ch) < 32 and ch not in "\t\n\r" for ch in text):
            continue
        text = text.replace("\r\n", "\n").replace("\r", "\n")
        if not text.strip():
            raise ValueError("Source is empty or whitespace-only")
        return text
    raise ValueError("Source cannot be decoded safely as UTF-8, BOM-marked UTF-16, or CP1256")


def natural_key(path: Path):
    return tuple((1, int(part)) if part.isdigit() else (0, part.casefold())
                 for part in re.split(r"(\d+)", path.name)) + ((0, path.name),)


def collect_inputs(inputs=None, input_dir=None) -> list[Path]:
    if (inputs is None) == (input_dir is None):
        raise ValueError("Specify exactly one of --inputs and --input-dir")
    if input_dir is not None:
        directory = Path(input_dir).expanduser().resolve(strict=True)
        if not directory.is_dir():
            raise ValueError("--input-dir must name a directory")
        candidates = sorted((p for p in directory.iterdir()
                             if p.is_file() and p.suffix.casefold() == ".txt"),
                            key=natural_key)
    else:
        candidates = [Path(p).expanduser() for p in inputs]
    if not candidates:
        raise ValueError("At least one TXT source is required")
    sources, seen = [], set()
    for candidate in candidates:
        path = candidate.resolve(strict=True)
        if not path.is_file() or candidate.suffix.casefold() != ".txt":
            raise ValueError(f"Source must be a readable TXT file: {candidate}")
        if path in seen:
            raise ValueError(f"Repeated resolved source path: {candidate}")
        seen.add(path)
        sources.append(path)
    return sources


def write_json_exclusive(path: Path, data) -> None:
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(data, stream, ensure_ascii=False, indent=2)
        stream.write("\n")


def prepare(inputs=None, input_dir=None, work_dir=None) -> dict:
    if work_dir is None:
        raise ValueError("A new or empty --work-dir is required")
    sources = collect_inputs(inputs, input_dir)
    requested_root = Path(work_dir).expanduser()
    if requested_root.is_symlink():
        raise ValueError("Work directory must not be a symbolic link")
    root = requested_root.resolve()
    if root.exists() and (not root.is_dir() or any(root.iterdir())):
        raise ValueError("Work directory must be new or truly empty; existing runs cannot be overwritten")
    # All input reads/decoding happen before the first output mutation.
    prepared = []
    for path in sources:
        if path == root or root in path.parents:
            raise ValueError(f"Source lies inside the work directory: {path}")
        raw = path.read_bytes()
        try:
            normalized = decode_source(raw)
        except ValueError as exc:
            raise ValueError(f"{path.name}: {exc}") from exc
        prepared.append((path, raw, normalized))
    root.mkdir(parents=True, exist_ok=True)
    lock = root / ".prepare-lock"
    # Exclusive claim plus a second emptiness check also prevents concurrent
    # preparation from silently replacing another run's snapshots or jobs.
    with lock.open("x", encoding="ascii") as stream:
        stream.write("single-use run preparation\n")
    if any(p != lock for p in root.iterdir()):
        lock.unlink()
        raise ValueError("Work directory changed during preparation; refusing to overwrite")
    run_id = str(uuid.uuid4())
    manifest_path = root / "manifest.json"
    protocol_path = (Path(__file__).resolve().parents[1] / "references" / "worker-protocol.md")
    for directory in ("sources", "analyses", "jobs"):
        (root / directory).mkdir()
    manifest = {"schema_version": 1, "run_id": run_id, "sources": []}
    jobs = []
    for order, (path, raw, normalized) in enumerate(prepared, 1):
        source_id = f"l{order:03d}"
        raw_path = f"sources/{source_id}.original.txt"
        normalized_path = f"sources/{source_id}.txt"
        analysis_path = f"analyses/{source_id}.json"
        job_path = f"jobs/{source_id}.json"
        normalized_bytes = normalized.encode("utf-8")
        digest = hashlib.sha256(normalized_bytes).hexdigest()
        with (root / raw_path).open("xb") as stream:
            stream.write(raw)
        with (root / normalized_path).open("xb") as stream:
            stream.write(normalized_bytes)
        manifest["sources"].append({
            "id": source_id, "order": order, "original_name": path.name,
            "raw_path": raw_path, "normalized_path": normalized_path,
            "raw_sha256": hashlib.sha256(raw).hexdigest(), "sha256": digest,
            "characters": len(normalized), "analysis_path": analysis_path,
            "job_path": job_path,
        })
        job = {
            "schema_version": 1, "run_id": run_id, "source_id": source_id,
            "source_sha256": digest, "input_path": str(root / normalized_path),
            "manifest_path": str(manifest_path), "output_path": str(root / analysis_path),
            "protocol_path": str(protocol_path), "source_order": order,
            "original_name": path.name,
        }
        write_json_exclusive(root / job_path, job)
        jobs.append(str(root / job_path))
    write_json_exclusive(manifest_path, manifest)
    lock.unlink()
    return {"manifest_path": str(manifest_path), "job_paths": jobs}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--inputs", nargs="+", help="Ordered TXT inputs; this order is preserved")
    group.add_argument("--input-dir", help="Nonrecursive TXT directory; natural filename order")
    parser.add_argument("--work-dir", required=True, help="New or truly empty single-use run directory")
    args = parser.parse_args(argv)
    try:
        result = prepare(args.inputs, args.input_dir, args.work_dir)
    except (OSError, ValueError) as exc:
        print(f"Preparation failed: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
