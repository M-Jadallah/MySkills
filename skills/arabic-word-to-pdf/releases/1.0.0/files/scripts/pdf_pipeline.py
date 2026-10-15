"""Merge Word exports numerically and add footer numbers and a thin page frame."""
from __future__ import annotations
import argparse
import csv
from io import BytesIO
import json
from pathlib import Path
import tempfile
import os
from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen import canvas


def build(args):
    folder = args.pdf_dir.resolve()
    rows = json.loads(args.manifest.read_text(encoding="utf-8-sig"))
    if not isinstance(rows, list) or not rows:
        raise ValueError("Manifest must be a non-empty list")
    rows.sort(key=lambda row: int(row["number"]))
    numbers = [int(row["number"]) for row in rows]
    if len(set(numbers)) != len(numbers):
        raise ValueError("Repeated lesson numbers")
    if Path(args.combined_name).name != args.combined_name or not args.combined_name.lower().endswith(".pdf"):
        raise ValueError("Combined name must be a simple PDF filename")
    if args.frame_inset <= 0 or args.footer_size <= 0 or args.footer_y <= args.frame_inset:
        raise ValueError("Footer must be inside a positive page frame")
    writer = PdfWriter()
    manifest = []
    page_offset = 0
    for row in rows:
        name = row["pdf"]
        if Path(name).name != name or name == args.combined_name:
            raise ValueError("Unsafe or colliding individual PDF name")
        reader = PdfReader(folder / name, strict=True)
        count = len(reader.pages)
        if count < 1 or count != int(row["word_pages"]):
            raise ValueError(f"Word/PDF page count mismatch: {name}")
        writer.append(reader, outline_item=f"الدرس {row['number']}")
        manifest.append({"الدرس": row["number"], "الملف": name, "عدد الصفحات": count,
                         "بداية الدرس": page_offset + 1, "نهاية الدرس": page_offset + count})
        page_offset += count
    if len(writer.pages) != page_offset:
        raise ValueError("Combined page count mismatch")
    buffer = BytesIO()
    overlay_canvas = canvas.Canvas(buffer, pageCompression=1)
    dimensions = []
    for index, page in enumerate(writer.pages):
        if page.rotation or float(page.mediabox.left) != 0 or float(page.mediabox.bottom) != 0:
            raise ValueError("Rotated or offset pages need a coordinate adaptation")
        width, height = float(page.mediabox.width), float(page.mediabox.height)
        if 2 * args.frame_inset >= min(width, height):
            raise ValueError("Frame inset exceeds page dimensions")
        dimensions.append((width, height))
        overlay_canvas.setPageSize((width, height))
        overlay_canvas.setStrokeColorRGB(0, 0, 0)
        overlay_canvas.setLineWidth(0.65)
        inset = args.frame_inset
        overlay_canvas.rect(inset, inset, width - 2 * inset, height - 2 * inset, fill=0, stroke=1)
        overlay_canvas.setFillColorRGB(0, 0, 0)
        overlay_canvas.setFont("Helvetica", args.footer_size)
        overlay_canvas.drawCentredString(width / 2, args.footer_y, str(index + 1))
        overlay_canvas.showPage()
    overlay_canvas.save()
    buffer.seek(0)
    overlays = PdfReader(buffer)
    for index, page in enumerate(writer.pages):
        contents = page.get_contents()
        before = list(contents.operations) if contents else []
        page.merge_page(overlays.pages[index], over=True)
        after = page.get_contents().operations
        if before and after[1:1 + len(before)] != before:
            raise ValueError(f"Original page content changed: {index + 1}")
    writer.add_metadata({"/Title": "جميع الدروس مرتبة مع إطار وترقيم"})
    writer.compress_identical_objects(remove_duplicates=True, remove_unreferenced=True)
    target = folder / args.combined_name
    handle, temporary = tempfile.mkstemp(prefix=".combined-", suffix=".pdf", dir=folder)
    os.close(handle)
    try:
        writer.write(temporary)
        writer.close()
        combined = PdfReader(temporary, strict=True)
        if len(combined.pages) != page_offset or len(combined.outline) != len(rows):
            raise ValueError("Page or bookmark count changed")
        for index, page in enumerate(combined.pages):
            footers = []
            def visitor(text, cm, tm, font, size):
                if text.strip() and abs(float(tm[5]) - args.footer_y) < 0.1:
                    footers.append(text.strip())
            page.extract_text(visitor_text=visitor)
            if str(index + 1) not in footers:
                raise ValueError(f"Missing footer number: {index + 1}")
            width, height = dimensions[index]
            expected_rect = [args.frame_inset, args.frame_inset,
                             width - 2 * args.frame_inset, height - 2 * args.frame_inset]
            if not any([float(v) for v in values] == expected_rect
                       for values, op in page.get_contents().operations if op == b"re"):
                raise ValueError(f"Missing page frame: {index + 1}")
        os.replace(temporary, target)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    with (folder / "فهرس الدروس والصفحات.csv").open("w", encoding="utf-8-sig", newline="") as stream:
        table = csv.DictWriter(stream, fieldnames=list(manifest[0]))
        table.writeheader()
        table.writerows(manifest)
    report = {"individual_pdfs": len(rows), "pages": page_offset, "bookmarks": len(rows),
              "centered_preserved": sum(int(r["centered_preserved"]) for r in rows),
              "page_numbers_verified": True, "frames_verified": True,
              "original_content_preserved": True, "combined": args.combined_name,
              "frame_inset_pt": args.frame_inset, "footer_y_pt": args.footer_y}
    (folder / "verification.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--pdf-dir", type=Path, required=True)
    parser.add_argument("--combined-name", default="جميع الدروس مرتبة.pdf")
    parser.add_argument("--frame-inset", type=float, default=8)
    parser.add_argument("--footer-y", type=float, default=25)
    parser.add_argument("--footer-size", type=float, default=11)
    build(parser.parse_args())
