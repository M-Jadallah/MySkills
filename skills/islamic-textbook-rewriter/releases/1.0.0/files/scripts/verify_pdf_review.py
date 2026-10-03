"""Check declared page-review coverage; cannot prove that an agent saw an image."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from prepare_pdf import parse_pages, read_json, sha256


def verify_review(manifest_path: str | Path, review_path: str | Path, *, pages: str | None = None) -> dict:
    manifest, review = read_json(Path(manifest_path)), read_json(Path(review_path))
    errors: list[str] = []
    fingerprint = manifest.get("source_sha256")
    if not fingerprint or review.get("source_sha256") != fingerprint:
        errors.append("سجل المراجعة لا يطابق مصدر PDF")
    source = Path(manifest.get("source_pdf", ""))
    if not source.is_file() or sha256(source) != fingerprint:
        errors.append("المصدر مفقود أو تغير بعد التحضير")
    selected = parse_pages(pages, manifest["total_pages"])
    rendered = {row["pdf_page"]: row for row in manifest.get("pages", [])}
    reviewed: dict[int, dict] = {}
    for row in review.get("pages", []):
        if row.get("pdf_page") in reviewed:
            errors.append(f"رقم صفحة مكرر في سجل المراجعة: {row.get('pdf_page')}")
        reviewed[row.get("pdf_page")] = row
    missing, unresolved = [], []
    for number in selected:
        image_path = rendered.get(number, {}).get("image_path")
        if not image_path or not Path(image_path).is_file():
            missing.append(number)
        row = reviewed.get(number)
        if row is None or row.get("status") != "reviewed":
            unresolved.append({"pdf_page": number, "status": row.get("status", "missing") if row else "missing", "notes": row.get("notes", "") if row else ""})
    if missing:
        errors.append("صفحات بلا صور كاملة موجودة: " + ", ".join(map(str, missing)))
    if unresolved:
        errors.append("صفحات لم يثبت اكتمال مراجعتها في السجل")
    return {"ok": not errors, "errors": errors, "required_pages": selected, "missing_images": missing, "unresolved_pages": unresolved, "scope": "declared coverage only; semantic/visual understanding is the agent's responsibility"}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--review", required=True)
    parser.add_argument("--pages")
    args = parser.parse_args()
    try:
        report = verify_review(args.manifest, args.review, pages=args.pages)
    except Exception as exc:
        report = {"ok": False, "errors": [str(exc)]}
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
