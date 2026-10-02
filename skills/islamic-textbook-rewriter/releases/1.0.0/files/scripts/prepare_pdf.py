"""Render PDF pages for agent vision and extract any existing text layer.

Rendering never marks pages as reviewed and does not perform OCR or semantic
analysis. Incremental batches are tied to the source file's SHA-256.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any

from utils import safe_filename

DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹،–—", "01234567890123456789,--")
ARABIC = re.compile(r"[\u0621-\u063a\u0641-\u064a\u0671]")


def parse_pages(spec: str | None, total: int) -> list[int]:
    if total < 1:
        raise ValueError("PDF لا يحتوي صفحات")
    if spec is None:
        return list(range(1, total + 1))
    out: set[int] = set()
    for part in spec.translate(DIGITS).split(","):
        match = re.fullmatch(r"\s*(\d+)\s*(?:-\s*(\d+)\s*)?", part)
        if not match:
            raise ValueError("صيغة الصفحات: 1-8 أو 1,3,5-7؛ الأرقام تبدأ من ١")
        first = int(match[1])
        last = int(match[2]) if match[2] else first
        if not 1 <= first <= last <= total:
            raise ValueError(f"نطاق الصفحات خارج الملف: {part.strip()}؛ عدد الصفحات {total}")
        out.update(range(first, last + 1))
    return sorted(out)


def parse_crop(spec: str | None) -> tuple[float, float, float, float] | None:
    if spec is None:
        return None
    try:
        parts = tuple(float(value.strip()) for value in spec.translate(DIGITS).split(","))
    except ValueError as exc:
        raise ValueError("إحداثيات القص أربع نسب بين ٠ و١") from exc
    if len(parts) != 4 or not (0 <= parts[0] < parts[2] <= 1 and 0 <= parts[1] < parts[3] <= 1):
        raise ValueError("القص left,top,right,bottom؛ نسب بين ٠ و١ ومساحة موجبة")
    return parts


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path: Path, data: Any) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def prepare_pdf(input_pdf: str | Path, output_dir: str | Path | None = None, *, pages: str | None = None, dpi: int = 200, crop: str | None = None) -> dict[str, Any]:
    try:
        import pymupdf as fitz
    except ImportError as exc:
        raise RuntimeError("مسار PDF يحتاج PyMuPDF؛ استخدم runtime مناسبًا أو ثبّت PyMuPDF من requirements.txt") from exc
    source = Path(input_pdf).resolve()
    if not source.is_file() or source.suffix.lower() != ".pdf":
        raise ValueError("مسار ملف PDF موجود مطلوب")
    if not 72 <= dpi <= 600:
        raise ValueError("دقة العرض يجب أن تكون بين ٧٢ و٦٠٠ نقطة")
    fingerprint = sha256(source)
    folder = Path(output_dir).resolve() if output_dir else source.parent / "pdf_reading" / (safe_filename(source.stem) + "-" + fingerprint[:10])
    manifest_path, review_path = folder / "manifest.json", folder / "review-log.json"
    previous = read_json(manifest_path) if manifest_path.exists() else {}
    review = read_json(review_path) if review_path.exists() else None
    for existing in (previous, review):
        if existing and existing.get("source_sha256") != fingerprint:
            raise ValueError("مجلد القراءة يخص نسخة PDF أخرى؛ استخدم مجلدًا جديدًا")
    clip_ratios = parse_crop(crop)
    with fitz.open(source) as document:
        if document.needs_pass:
            raise ValueError("PDF مقفل بكلمة مرور؛ يلزم مصدر قابل للفتح")
        total = document.page_count
        selected = parse_pages(pages, total)
        folder.mkdir(parents=True, exist_ok=True)
        page_records = {row["pdf_page"]: row for row in previous.get("pages", [])}
        crop_records = previous.get("crops", [])
        created: list[str] = []
        for page_number in selected:
            page = document.load_page(page_number - 1)
            if clip_ratios:
                left, top, right, bottom = clip_ratios
                rect = page.rect
                clip = fitz.Rect(rect.x0 + left * rect.width, rect.y0 + top * rect.height, rect.x0 + right * rect.width, rect.y0 + bottom * rect.height)
                key = "-".join(f"{v:g}".replace(".", "p") for v in clip_ratios)
                image_path = folder / f"page-{page_number:04d}.crop-{key}-{dpi}dpi.png"
                pix = page.get_pixmap(dpi=dpi, clip=clip, alpha=False, annots=True)
                pix.save(image_path)
                crop_records = [r for r in crop_records if r.get("image_path") != str(image_path)]
                crop_records.append({"pdf_page": page_number, "ratios": list(clip_ratios), "dpi": dpi, "image_path": str(image_path), "width_px": pix.width, "height_px": pix.height})
                created.append(str(image_path))
                continue
            image_path = folder / f"page-{page_number:04d}.png"
            text_path = folder / f"page-{page_number:04d}.txt"
            blocks_path = folder / f"page-{page_number:04d}.blocks.json"
            pix = page.get_pixmap(dpi=dpi, alpha=False, annots=True)
            pix.save(image_path)
            extraction_error = None
            try:
                text = page.get_text("text", sort=True)
                blocks = [{"bbox": list(b[:4]), "text": b[4]} for b in page.get_text("blocks") if len(b) > 6 and b[6] == 0]
            except Exception as exc:
                text, blocks = "", []
                extraction_error = str(exc)
            text_path.write_text(text, encoding="utf-8")
            write_json(blocks_path, {"pdf_page": page_number, "coordinate_system": "PDF points; extraction order is not verified reading order", "blocks": blocks})
            count = len(text.strip())
            status = "unavailable" if extraction_error else ("none" if count == 0 else ("sparse" if count < 80 else "present"))
            if text.count("\ufffd") > max(2, count * 0.02):
                status = "suspicious"
            page_records[page_number] = {
                "pdf_page": page_number, "pdf_label": page.get_label() or None,
                "image_path": str(image_path), "text_path": str(text_path), "blocks_path": str(blocks_path),
                "dpi": dpi, "width_px": pix.width, "height_px": pix.height, "rotation": page.rotation,
                "text_characters": count, "arabic_letters": len(ARABIC.findall(text)),
                "text_layer_status": status, "text_extraction_error": extraction_error,
                "visual_reading_required": True,
            }
            created.append(str(image_path))
        manifest = {
            "source_pdf": str(source), "source_sha256": fingerprint, "total_pages": total,
            "pages": [page_records[n] for n in sorted(page_records)], "crops": crop_records,
            "unrendered_pages": [n for n in range(1, total + 1) if n not in page_records],
            "review_log": str(review_path),
        }
        write_json(manifest_path, manifest)
        if review is None:
            write_json(review_path, {"source_sha256": fingerprint, "pages": [{"pdf_page": n, "status": "pending", "printed_page": None, "lessons": [], "notes": ""} for n in range(1, total + 1)]})
    return {"ok": True, "source_pdf": str(source), "total_pages": total, "selected_pages": selected, "created_images": created, "manifest": str(manifest_path), "review_log": str(review_path), "rendered_full_pages": sorted(page_records), "unrendered_pages": manifest["unrendered_pages"], "visual_review_complete": False, "message": "الصور جاهزة؛ افتحها واقرأها ثم حدّث سجل المراجعة. التحضير لا ينفذ OCR ولا يثبت القراءة."}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True)
    parser.add_argument("--output-dir")
    parser.add_argument("--pages")
    parser.add_argument("--dpi", type=int, default=200)
    parser.add_argument("--crop", help="Relative left,top,right,bottom in [0,1]")
    args = parser.parse_args()
    try:
        result = prepare_pdf(args.input, args.output_dir, pages=args.pages, dpi=args.dpi, crop=args.crop)
    except Exception as exc:
        result = {"ok": False, "error": str(exc)}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
