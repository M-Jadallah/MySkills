#!/usr/bin/env python3
"""Chem Spectrum Lab - Step 01 extraction helper.

Extracts a chemistry lesson PDF into a faithful, fully-structured Markdown
that becomes the SINGLE SOURCE OF TRUTH for every later lab step.

It:
  * extracts text with correct Arabic RTL (arabic_reshaper + bidi),
  * renders every page to a PNG so a vision agent can describe diagrams,
    equations, and images that text extraction misses,
  * pulls embedded raster images,
  * auto-detects tables,
  * and ASSEMBLES `lesson-XX.md` from the template, filling theory text
    from the (RTL-corrected) extracted text.

Usage:
    python extract_pdf.py "<PDF_PATH>" [--out <dir>] [--dpi <int>]

Writes into <out> (default: <pdf_dir>/<stem>/):
    lesson-XX.md          <- the canonical source of truth
    images/               embedded raster images (PNG)
    pages/               full-page render PNGs for vision description
    _raw/
        per_page_text.md  RTL-corrected text per page
        tables.md         auto-detected tables as Markdown
        images_manifest.md image -> page mapping (agent fills description)
        metadata.json     page count, image count, table pages
"""
import argparse, json, os, pathlib, re, sys

try:
    import fitz  # PyMuPDF
except ImportError:
    sys.exit("PyMuPDF is required. Install it with:  pip install pymupdf")

try:
    import arabic_reshaper
    from bidi.algorithm import get_display
    HAVE_RTL = True
except ImportError:
    HAVE_RTL = False


def fix_rtl(text):
    """Correct Arabic shaping/reordering for text extraction."""
    if not text:
        return ""
    if HAVE_RTL:
        try:
            return get_display(arabic_reshaper.reshape(text))
        except Exception:
            return text
    return text


TEMPLATE = """# الدرس {XX}: {TITLE}

## معلومات الدرس
- **الصف:** التوجيهي
- **الفصل:** [الفصل]
- **الوحدة:** [الوحدة]
- **عدد الصفحات في الأصل:** {PAGES}
- **تاريخ الاستخراج:** {DATE}

---

## الأهداف التعليمية
[املأ الأهداف من بداية الدرس]

---

## المحتوى النظري

### الفقرة 1: [عنوان/موضوع الفقرة]
{THEORY}

---

## المعادلات الكيميائية
[ستُضاف المعادلات بعد وصف صور المعادلات/النص]

---

## الصور والرسومات
[ستُضاف الصور وأوصافها بعد معالجة مجلد pages/ والصور المستخرجة]

---

## الجداول
{TABLES}

---

## التجارب العملية المذكورة
[ستُملأ من النص]

---

## الأمثلة المحلولة
[ستُملأ من النص]

---

## المصطلحات والتعريفات
| المصطلح | التعريف |
|---------|---------|
|         |         |

---

## التمارين والأسئلة
[ستُملأ من النص]

---

## ملاحظات المدرس
> **⚠️ هذا القسم منفصل ويحتوي على ملاحظات مختصرة جداً لا تخرج عن المحتوى.**

- [ملاحظة]

---

## ملاحظات إضافية
[أي معلومات إضافية أو سياق مهم من الدرس]
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pdf", help="Path to the chemistry lesson PDF")
    ap.add_argument("--out", default=None, help="Output folder (default: <pdf_dir>/<stem>/)")
    ap.add_argument("--dpi", type=int, default=110, help="DPI for page renders (default 110)")
    ap.add_argument("--xx", default=None, help="Lesson number, e.g. 03 (default: parsed from filename or 01)")
    args = ap.parse_args()

    doc = fitz.open(args.pdf)
    stem = os.path.splitext(os.path.basename(args.pdf))[0]
    out = args.out or os.path.join(os.path.dirname(os.path.abspath(args.pdf)), stem)
    img_dir = os.path.join(out, "images")
    pages_dir = os.path.join(out, "_raw", "pages") if False else os.path.join(out, "pages")
    raw_dir = os.path.join(out, "_raw")
    for d in (img_dir, pages_dir, raw_dir):
        os.makedirs(d, exist_ok=True)

    # lesson number
    m = re.search(r"(\d+)", stem)
    xx = args.xx or (m.group(1) if m else "01")
    xx = xx.zfill(2)

    pages_text = []
    tables_md = []
    manifest = []
    extracted_images = []

    for pno in range(doc.page_count):
        page = doc[pno]
        pnum = pno + 1

        # 1) text (RTL-corrected)
        raw = page.get_text("text")
        fixed = fix_rtl(raw)
        pages_text.append((pnum, fixed))

        # 2) embedded images
        for iidx, img in enumerate(page.get_images(full=True), 1):
            xref = img[0]
            try:
                pix = fitz.Pixmap(doc, xref)
                if pix.n - pix.alpha >= 4:
                    pix = fitz.Pixmap(fitz.csRGB, pix)
                fname = f"page-{pnum:02d}-img-{iidx:02d}.png"
                pix.save(os.path.join(img_dir, fname))
                manifest.append({"file": fname, "page": pnum, "index_on_page": iidx, "kind": "embedded"})
                extracted_images.append(fname)
            except Exception as e:
                pages_text.append((pnum, f"\n[image xref {xref} failed: {e}]\n"))

        # 3) tables
        try:
            for t in page.find_tables().tables:
                tables_md.append((pnum, fix_rtl(t.to_markdown())))
        except Exception:
            pass

        # 4) full-page render for vision description
        try:
            mat = fitz.Matrix(args.dpi / 72.0, args.dpi / 72.0)
            pix = page.get_pixmap(matrix=mat)
            pix.save(os.path.join(pages_dir, f"page-{pnum:02d}.png"))
        except Exception as e:
            pages_text.append((pnum, f"\n[page render failed: {e}]\n"))

    # write text
    with open(os.path.join(raw_dir, "per_page_text.md"), "w", encoding="utf-8") as f:
        for pnum, t in pages_text:
            f.write(f"\n\n<!-- ===== PAGE {pnum} ===== -->\n\n")
            f.write(t if t.strip() else f"_(page {pnum}: no extractable text - see pages/page-{pnum:02d}.png)_\n")

    # write tables
    with open(os.path.join(raw_dir, "tables.md"), "w", encoding="utf-8") as f:
        if tables_md:
            for pnum, md in tables_md:
                f.write(f"\n\n<!-- TABLES FROM PAGE {pnum} -->\n\n{md}\n")
        else:
            f.write("_No tables auto-detected. Inspect pages/ for table-like layouts and transcribe manually._\n")

    # manifest
    with open(os.path.join(raw_dir, "images_manifest.md"), "w", encoding="utf-8") as f:
        f.write("# Images manifest\n\nAgent: for every image write an accurate Arabic description covering what it shows, the data in it, and its importance in the lesson.\n\n")
        if manifest:
            for mm in manifest:
                f.write(f"- `{mm['file']}` - page {mm['page']}, image #{mm['index_on_page']} on that page\n")
                f.write(f"  - **الوصف:** _(املأ: ما الذي تُظهره الصورة، البيانات فيها، أهميتها)_\n")
        else:
            f.write("_No embedded images extracted. If the lesson has diagrams, they may be vector-only - inspect pages/ and describe them from the renders._\n")

    meta = {
        "source_pdf": os.path.abspath(args.pdf),
        "page_count": doc.page_count,
        "image_count": len(manifest),
        "table_pages": [p for p, _ in tables_md],
        "extracted_images": extracted_images,
        "rtl_corrected": HAVE_RTL,
    }
    with open(os.path.join(raw_dir, "metadata.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

    # 5) ASSEMBLE lesson-XX.md (single source of truth)
    theory = "\n\n".join(t for _, t in pages_text if t.strip())
    if not theory.strip():
        theory = "_(لم يُستخرج نص قابل للقراءة — راجع مجلد pages/ واوصفه بوكيل الرؤية)_\n"
    tables_block = ""
    if tables_md:
        for pnum, md in tables_md:
            tables_block += f"\n<!-- من الصفحة {pnum} -->\n{md}\n"
    else:
        tables_block = "| العمود 1 | العمود 2 |\n|----------|----------|\n| ... | ... |\n"
    from datetime import date
    md_text = TEMPLATE.format(
        XX=xx, TITLE=stem, PAGES=doc.page_count,
        DATE=date.today().isoformat(), THEORY=theory, TABLES=tables_block,
    )
    with open(os.path.join(out, f"lesson-{xx}.md"), "w", encoding="utf-8") as f:
        f.write(md_text)

    print(json.dumps(meta, ensure_ascii=False))
    print(f"Outputs in: {out}")
    print(f"CANONICAL: {os.path.join(out, f'lesson-{xx}.md')}")


if __name__ == "__main__":
    main()
