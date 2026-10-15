---
name: chem-spectrum-lab-01-pdf-to-md
description: Extract chemistry PDF lessons into canonical Markdown.
version: 0.1.0
author: Mutja, Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [chem-spectrum-lab, pdf, markdown, chemistry, tawjihi]
    related_skills: []
---

# Chem Spectrum Lab — Step 01: PDF → Markdown

Converts a Jordanian Tawjihi chemistry lesson PDF into one faithful, fully-structured Markdown file that becomes the **single source of truth** for every later lab step (lab manual, slides, Word doc). It extracts every paragraph, equation (as LaTeX), image (with an accurate Arabic description), table, solved example, experiment, and exercise — no summarization, no added content. A helper script does the mechanical extraction; the agent does the structuring, LaTeX conversion, and image description via vision.

## When to Use

- User supplies a chemistry lesson PDF (Jordanian Tawjihi textbook) and wants a complete Markdown transcript.
- This is **step 01** of the `chem-spectrum-lab` pipeline — run it before any downstream skill.
- Don't use for: non-chemistry PDFs, already-Markdown sources, or summarization requests (this skill is extractive, not abridging).

## Prerequisites

- Python 3.11+ with `pip`. Install the extractor once: `pip install pymupdf`.
- The `vision_analyze` tool (built into Hermes) for describing extracted images and reading equation/diagram renders.
- The lesson PDF path.

## How to Run

Invoke through the `terminal` tool to run the bundled helper, then assemble with `write_file`/`patch`:

```bash
python "C:/Users/mutja/AppData/Local/hermes/skills/chem-spectrum-lab-01-pdf-to-md/scripts/extract_pdf.py" "<PDF_PATH>"
```

The helper writes its working folder next to the PDF (`<pdf_dir>/<stem>/`). After it finishes, follow the Procedure to produce `<stem>/lesson-XX.md`.

## Quick Reference

- Extract raw material: `terminal` → `extract_pdf.py <PDF>`
- Read extracted text: `read_file` on `<stem>/_raw/per_page_text.md`
- Describe images: `vision_analyze` on each `<stem>/images/*.png`
- Read equations/diagrams: `vision_analyze` on `<stem>/pages/*.png`
- Write final file: `write_file` to `<stem>/lesson-XX.md` using `references/template.md`
- Verify completeness: checklist in Verification

## Procedure

1. **Install/confirm the extractor.** Run `pip install pymupdf arabic-reshaper python-bidi`. Check completion: `python -c "import fitz, arabic_reshaper, bidi"` succeeds.
2. **Run the helper** on the PDF (see How to Run). Completion: `<stem>/` exists with `lesson-XX.md`, `images/`, `pages/`, `_raw/` and a printed `metadata.json` (page count, image count, RTL flag).
3. **Read the raw text** (`_raw/per_page_text.md`) page by page — now RTL-corrected. Completion: you can enumerate every section the lesson contains.
4. **Detect chemical equations via vision (MANDATORY).** Equations are usually vector diagrams/images inside the PDF and will NOT appear in the text. Use `vision_analyze` on each `pages/page-NN.png` (and `images/*.png`) and transcribe every equation found into a balanced LaTeX block `$$2H_2 + O_2 \rightarrow 2H_2O$$`. Verify atom balance. Completion: every equation in the lesson appears as a balanced `$$...$$` block in `lesson-XX.md`.
5. **Describe every image.** For each file in `images/`, run `vision_analyze` and write the Arabic description into `_raw/images_manifest.md`, covering: what it shows, the data in it, its importance. If none were extracted but the lesson has diagrams, describe them from the `pages/` renders instead. Completion: manifest has one filled description per image.
6. **Transcribe tables.** Read `_raw/tables.md`; if empty, inspect `pages/*.png` and transcribe via `vision_analyze`. Completion: every table is a faithful Markdown table.
7. **Enrich the canonical file.** The helper already created `<stem>/lesson-XX.md`; verify and fill every section: lesson info, objectives, full theory (no summarization), equations, images+descriptions, tables, experiments, solved examples, terms/definitions, exercises, and a separate brief teacher-notes section. Use RTL Arabic throughout. Completion: file matches the template structure with no empty required section.
8. **Generate the brand logo** (once, shared by all lessons): run `make_logo.py --out "<frontend>/assets"` from the orchestrator skill to write `logo.png` + `logo-dark.png`. Completion: both logo files exist.
9. **Self-check against the acceptance criteria** in Verification. Completion: every checkbox is satisfied or explicitly noted as not-applicable for this lesson.

## Pitfalls

- **Embedded images vs. vector diagrams:** `get_images` extracts raster/embedded images only. Pure-vector diagrams won't appear in `images/` — describe them from the `pages/` renders instead; don't report "no images."
- **Scanned/flattened pages:** if `per_page_text.md` is empty, the PDF is image-only. Rely on `pages/*.png` + `vision_analyze` to transcribe everything; flag this to the user.
- **Equation balance:** never emit an unbalanced `$$...$$`; verify atoms on both sides.
- **No added content:** teacher notes and all text must come only from the lesson. Do not enrich with outside chemistry knowledge.
- **No summarization:** long paragraphs may be split into bullet points, but meaning and every number must be preserved verbatim.
- **LaTeX arrows:** use `\rightarrow` (not `->` or `→`) inside `$$...$$`.

## Verification

- [ ] Every text paragraph from the PDF is present in the Markdown.
- [ ] Every chemical equation appears as a balanced LaTeX `$$...$$` block.
- [ ] Every image has an accurate Arabic description (or is described from page renders).
- [ ] Every table is transcribed as a Markdown table with intact data.
- [ ] Every solved example, experiment, and exercise is included.
- [ ] The `## ملاحظات المدرس` section exists, is brief, and stays within the lesson content.
- [ ] Output file is `<stem>/lesson-XX.md` following `references/template.md` exactly.
