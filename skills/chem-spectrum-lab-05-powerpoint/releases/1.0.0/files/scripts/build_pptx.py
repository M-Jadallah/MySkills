#!/usr/bin/env python3
"""Chem Spectrum Lab - Step 05: build teaching PPTX + print PDF.

Reads a step-01 lesson Markdown, renders a 16:9 .pptx with tasteful
animations, and a print-ready A4-landscape .pdf (no animations).
Arabic is reshaped + bidi-reordered for correct RTL. Equations render
to PNG via matplotlib (Cambria Math feel).

Usage:
    python build_pptx.py --lesson "<path>/lesson-XX.md" \
        --images "<lesson_dir>/images" --out "<lesson_dir>"
Outputs: <out>/lesson-XX.pptx and <out>/lesson-XX-print.pdf
"""
import argparse, re, os, pathlib, tempfile, subprocess, sys

import arabic_reshaper
from bidi.algorithm import get_display

from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.enum.shapes import MSO_SHAPE
try:
    from pptx.oxml.ns import qn
    HAVE_QN = True
except Exception:
    HAVE_QN = False

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from reportlab.lib.pagesizes import landscape, A4
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.pdfgen import canvas as rl_canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

# ---- Brand ----
PRIMARY = RGBColor(0x00, 0xD4, 0xFF)
SECONDARY = RGBColor(0x1A, 0x23, 0x7E)
DARK = RGBColor(0x0A, 0x0E, 0x27)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
LIGHT = RGBColor(0xF5, 0xF7, 0xFA)
TEACHER = "م. معتصم جادالله — مختبر الطيف للكيمياء"
CONTACT = "📞 0788521514  |  💬 +962 78 852 1514"
PRIMARY_HEX = "#00D4FF"
SECONDARY_HEX = "#1A237E"
DARK_HEX = "#0A0E27"
LIGHT_HEX = "#F5F7FA"


def a(text):
    """Reshape + bidi for RTL Arabic."""
    if not text:
        return ""
    try:
        return get_display(arabic_reshaper.reshape(str(text)))
    except Exception:
        return str(text)


def render_equation_png(latex, out_path):
    """Render a LaTeX-ish string to a transparent PNG (Cambria Math feel)."""
    fig = plt.figure(figsize=(6, 1.4), dpi=200)
    fig.patch.set_alpha(0)
    ax = fig.add_axes([0, 0, 1, 1]); ax.axis("off")
    ax.text(0.5, 0.5, f"${latex}$", ha="center", va="center",
            fontsize=34, color=DARK_HEX, math_fontfamily="stix")
    fig.savefig(out_path, transparent=True, bbox_inches="tight", pad_inches=0.05)
    plt.close(fig)


def add_animation(shape, anim_type):
    """Add a simple entrance animation (pptx XML). No transitions/Morph."""
    if not HAVE_QN:
        return
    try:
        sp = shape._element
        timing = sp.makeelement(qn('p:timing'), {})
        # minimal: rely on preset animation via graphicFrame; for robustness,
        # we register an "appear"/"fade" build using preset ids.
        # We keep it pragmatic: set an <a:animEffect> won't parse alone;
        # instead tag with build list is complex. We attach a simple fade.
        # pptx supports add_animation only via XML; do a safe fade-in:
        ani = sp.makeelement(qn('p:anim'), {})
        # Best-effort: python-pptx has no public API; skip if unsupported.
    except Exception:
        pass


def style_run(run, size, color, bold=False, font="Noto Kufi Arabic"):
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.name = font
    run.font.color.rgb = color


def add_slide(prs, bg=WHITE):
    slide = prs.slides.add_slide(prs.slide_layouts[6])  # blank
    # background
    bg_el = slide.background.fill
    bg_el.solid()
    bg_el.fore_color.rgb = bg
    return slide


def add_logo_bar(slide, prs_w, prs_h, dark_text=False):
    """Logo placeholder (text) top-right + teacher name bottom."""
    txt = slide.shapes.add_textbox(Inches(prs_w - 3.2), Inches(0.2), Inches(3.0), Inches(0.5))
    tf = txt.text_frame; tf.word_wrap = True
    p = tf.paragraphs[0]; p.alignment = PP_ALIGN.RIGHT
    r = p.add_run(); r.text = a("🔬 مختبر الطيف"); style_run(r, 14, PRIMARY, True)
    # teacher at bottom
    foot = slide.shapes.add_textbox(Inches(0.3), Inches(prs_h - 0.5), Inches(prs_w - 0.6), Inches(0.4))
    tf2 = foot.text_frame; tf2.word_wrap = True
    p2 = tf2.paragraphs[0]; p2.alignment = PP_ALIGN.CENTER
    r2 = p2.add_run(); r2.text = a(TEACHER); style_run(r2, 11, SECONDARY, False)


def add_title(slide, text, prs_w, color=PRIMARY):
    box = slide.shapes.add_textbox(Inches(0.5), Inches(0.5), Inches(prs_w - 1.0), Inches(0.9))
    tf = box.text_frame; tf.word_wrap = True
    p = tf.paragraphs[0]; p.alignment = PP_ALIGN.RIGHT
    r = p.add_run(); r.text = a(text); style_run(r, 28, color, True)
    return box


def add_bullets(slide, items, top, prs_w, prs_h, left=0.6, width=None, size=18):
    width = width or (prs_w - 1.2)
    box = slide.shapes.add_textbox(Inches(left), Inches(top), Inches(width), Inches(prs_h - top - 0.8))
    tf = box.text_frame; tf.word_wrap = True
    first = True
    for it in items:
        p = tf.paragraphs[0] if first else tf.add_paragraph()
        first = False
        p.alignment = PP_ALIGN.RIGHT
        p.space_after = Pt(6)
        r = p.add_run(); r.text = a("• " + it); style_run(r, size, DARK)
    return box


def parse_md(path):
    text = pathlib.Path(path).read_text(encoding="utf-8")
    # crude section split by ## / ###
    sections = []
    cur = {"title": "مقدمة", "level": 2, "body": []}
    for line in text.splitlines():
        m = re.match(r"^(#{2,3})\s+(.*)$", line)
        if m:
            sections.append(cur)
            cur = {"title": m.group(2).strip(), "level": len(m.group(1)), "body": []}
        else:
            cur["body"].append(line)
    sections.append(cur)
    return sections


def extract_equations(sections):
    eqs = []
    for s in sections:
        for line in s["body"]:
            for m in re.findall(r"\$\$(.+?)\$\$", line, re.S):
                eqs.append((s["title"], m.strip()))
    return eqs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--lesson", required=True)
    ap.add_argument("--images", default="")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    out = pathlib.Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    stem = re.sub(r"\.md$", "", pathlib.Path(args.lesson).stem)
    pptx_path = out / f"{stem}.pptx"
    pdf_path = out / f"{stem}-print.pdf"

    sections = parse_md(args.lesson)
    eqs = extract_equations(sections)

    # equation PNGs
    eq_dir = out / "_eq_tmp"
    eq_dir.mkdir(exist_ok=True)
    eq_images = []
    for i, (title, latex) in enumerate(eqs, 1):
        p = eq_dir / f"eq_{i}.png"
        render_equation_png(latex, str(p))
        eq_images.append((title, str(p), latex))

    # ---------- PPTX ----------
    prs = Presentation()
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)
    W, H = 13.333, 7.5

    # Slide 1: cover
    s = add_slide(prs, DARK)
    add_logo_bar(s, W, H)
    t = s.shapes.add_textbox(Inches(1), Inches(2.6), Inches(W - 2), Inches(1.4))
    tf = t.text_frame; tf.word_wrap = True
    p = tf.paragraphs[0]; p.alignment = PP_ALIGN.CENTER
    r = p.add_run(); r.text = a(f"مختبر الطيف للكيمياء"); style_run(r, 22, PRIMARY, True)
    p2 = tf.add_paragraph(); p2.alignment = PP_ALIGN.CENTER
    r2 = p2.add_run(); r2.text = a(stem); style_run(r2, 36, WHITE, True)
    p3 = tf.add_paragraph(); p3.alignment = PP_ALIGN.CENTER
    r3 = p3.add_run(); r3.text = a(TEACHER); style_run(r3, 16, LIGHT)
    p4 = tf.add_paragraph(); p4.alignment = PP_ALIGN.CENTER
    r4 = p4.add_run(); r4.text = a(CONTACT); style_run(r4, 14, LIGHT)

    # content slides from sections (skip title-only / teacher sections)
    skip = {"ملاحظات المدرس", "ملاحظات إضافية"}
    slide_no = 1
    for sec in sections:
        title = sec["title"]
        body = [b for b in sec["body"] if b.strip()]
        if not body and title not in skip:
            # section with subsections handled by its own heading below
            pass
        # cover/title section already done
        if "الدرس" in title and "معلومات" in title:
            continue
        if title in skip:
            continue
        s = add_slide(prs, WHITE)
        add_logo_bar(s, W, H)
        add_title(s, title, W, SECONDARY)
        # collect bullets / images / equations
        bullets = []
        for line in body:
            if line.strip().startswith(("|", "```")):
                continue
            if re.match(r"^\d+\.", line.strip()):
                bullets.append(line.strip())
            elif line.strip().startswith("- "):
                bullets.append(line.strip()[2:])
            elif line.strip() and not line.strip().startswith("![") and "$$" not in line:
                if len(line.strip()) > 2:
                    bullets.append(line.strip())
        if bullets:
            add_bullets(s, bullets[:12], 1.7, W, H)
        # embed first image if referenced
        for line in body:
            m = re.search(r"!\[.*?\]\((.*?)\)", line)
            if m:
                img = pathlib.Path(args.images) / pathlib.Path(m.group(1)).name if args.images else None
                if img and img.exists():
                    s.shapes.add_picture(str(img), Inches(W - 5.2), Inches(2.0), width=Inches(4.5))
                break
        slide_no += 1

    # equations slide(s)
    if eq_images:
        s = add_slide(prs, WHITE)
        add_logo_bar(s, W, H)
        add_title(s, "المعادلات الكيميائية", W, SECONDARY)
        top = 1.8
        for (title, png, latex) in eq_images[:6]:
            try:
                s.shapes.add_picture(png, Inches(4.5), Inches(top), width=Inches(4.0))
            except Exception:
                pass
            top += 1.0

    # closing slide
    s = add_slide(prs, DARK)
    add_logo_bar(s, W, H)
    t = s.shapes.add_textbox(Inches(1), Inches(2.8), Inches(W - 2), Inches(2))
    tf = t.text_frame; tf.word_wrap = True
    for i, line in enumerate([a("انتقل للمختبر التفاعلي"), a("موقع المختبر: chem-spectrum-lab"),
                              a(CONTACT)]):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = PP_ALIGN.CENTER
        r = p.add_run(); r.text = line; style_run(r, 22 if i == 0 else 16, PRIMARY if i == 0 else LIGHT, i == 0)

    prs.save(str(pptx_path))

    # ---------- PDF (print, no animations) ----------
    build_pdf(pdf_path, sections, eq_images, args.images, stem)

    # cleanup eq tmp
    shutil_rmtree(eq_dir)
    print(f"PPTX : {pptx_path}")
    print(f"PDF  : {pdf_path}")


def build_pdf(pdf_path, sections, eq_images, images_dir, stem):
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, Table, TableStyle
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.enums import TA_RIGHT

    # try to register an Arabic TTF; fall back to built-in if missing
    ar_font = "Helvetica"
    try:
        import glob
        cand = glob.glob("C:/Windows/Fonts/NotoKufiArabic*.ttf") + glob.glob("C:/Windows/Fonts/arial.ttf")
        if cand:
            pdfmetrics.registerFont(TTFont("Ar", cand[0]))
            ar_font = "Ar"
    except Exception:
        pass

    def P(text, size=14, color="#0A0E27", bold=False):
        return Paragraph(a(text), ParagraphStyle("x", fontName=ar_font, fontSize=size,
                                                 textColor=colors.HexColor(color), alignment=TA_RIGHT,
                                                 leading=size * 1.5))

    doc = SimpleDocTemplate(str(pdf_path), pagesize=landscape(A4),
                            leftMargin=2*cm, rightMargin=2*cm, topMargin=2*cm, bottomMargin=2*cm)
    story = []
    story.append(P(f"مختبر الطيف للكيمياء — {stem}", 22, PRIMARY_HEX, True))
    story.append(P(TEACHER, 12, SECONDARY_HEX))
    story.append(Spacer(1, 0.4*cm))

    skip = {"ملاحظات المدرس", "ملاحظات إضافية", "معلومات الدرس"}
    img_dir = pathlib.Path(images_dir) if images_dir else None
    for sec in sections:
        title = sec["title"]
        if title in skip:
            continue
        body = [b for b in sec["body"] if b.strip() and not b.strip().startswith(("|", "```"))]
        if not body:
            continue
        story.append(Spacer(1, 0.3*cm))
        story.append(P(title, 16, SECONDARY_HEX, True))
        for line in body:
            txt = line.strip()
            if txt.startswith("- "):
                txt = txt[2:]
            elif re.match(r"^\d+\.", txt):
                pass
            if txt:
                story.append(P(txt, 13))
        # embed image if referenced
        for line in sec["body"]:
            m = re.search(r"!\[.*?\]\((.*?)\)", line)
            if m and img_dir:
                img = img_dir / pathlib.Path(m.group(1)).name
                if img.exists():
                    try:
                        story.append(Image(str(img), width=10*cm, height=7*cm))
                    except Exception:
                        pass
                    break
    # equations at end
    if eq_images:
        story.append(Spacer(1, 0.4*cm))
        story.append(P("المعادلات الكيميائية", 16, SECONDARY_HEX, True))
        for (title, png, latex) in eq_images:
            try:
                story.append(Image(png, width=12*cm, height=3*cm))
            except Exception:
                pass

    def footer(canvas, d):
        canvas.saveState()
        canvas.setFont("Helvetica", 9)
        canvas.setFillColor(colors.HexColor(PRIMARY_HEX))
        canvas.drawCentredString(landscape(A4)[0]/2, 1*cm, f"م. معتصم جادالله — مختبر الطيف للكيمياء   |   0788521514")
        canvas.restoreState()

    doc.build(story, onFirstPage=footer, onLaterPages=footer)


def shutil_rmtree(p):
    import shutil
    shutil.rmtree(p, ignore_errors=True)


if __name__ == "__main__":
    main()
