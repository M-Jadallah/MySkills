---
name: chem-spectrum-lab-06-word
description: Build a professional Word study docx from lesson Markdown.
version: 0.1.0
author: Mutja, Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [chem-spectrum-lab, word, docx, tawjihi]
    related_skills: []
---

# Chem Spectrum Lab — Step 06: Word Document

Reads the comprehensive lesson Markdown from **step 01** and produces a single professional, fully-editable `.docx` — the deep-study reference (unlike the quick slides of step 05 or the interactive lab of steps 02–04). It follows a strict simple→complex progression (cover → mind map → objectives → theory → equations → tables → experiments → solved examples → summary → exercises → glossary → contacts), applies the unified "مختبر الطيف" brand, is RTL, A4-print-ready, with header/footer on every page and writing space under exercises.

## When to Use

- You have a `lesson-XX.md` from `chem-spectrum-lab-01-pdf-to-md` and want a Word study document.
- This is **step 06** of the `chem-spectrum-lab` pipeline — independent of steps 02–05 (works straight from the step-01 source).
- Don't use for: the interactive lab (02–04), the PPTX/PDF (05), or PDF→Markdown (01).

## Prerequisites

- The step-01 output `lesson-XX.md`.
- Python 3.11+ with: `pip install python-docx arabic-reshaper python-bidi matplotlib`.
- The lesson's extracted images (from step 01, in `images/`) for embedding.

## How to Run

```bash
python "C:/Users/mutja/AppData/Local/hermes/skills/chem-spectrum-lab-06-word/scripts/build_docx.py" \
  --lesson "<path>/lesson-XX.md" \
  --images "<lesson_dir>/images" \
  --out "<lesson_dir>"
```

This writes `<lesson_dir>/lesson-XX.docx`. Equations are rendered as PNG (matplotlib) and embedded; Arabic is reshaped/reordered for RTL. Tables get the brand header style; note/warning/success boxes use the specified tints.

## Quick Reference

- Build: `terminal` → `build_docx.py --lesson <md> --images <dir> --out <dir>`
- Structure spec + box colors + icons: `read_file` `references/template.md`
- Brand colors/logo/teacher: `references/brand.md` (mirrors steps 03–05)
- RTL: handled inside the script via `arabic_reshaper` + `bidi.algorithm`; never hand-flip text.
- One output: `.docx` (editable in Word, A4).

## Procedure

1. **Confirm deps** (`python -c "import docx, arabic_reshaper, bidi"`). Completion: import succeeds.
2. **Parse `lesson-XX.md`** into the canonical sections. Completion: cover, mind map, objectives, theory, equations, tables, experiments, examples, summary, exercises, glossary, contacts all map.
3. **Create the document** with python-docx: A4 page size, 2.5cm margins, RTL section, brand fonts/colors. Completion: file opens in Word.
4. **Build the cover** (section 1): logo + lesson title + "الصف: التوجيهي - الأردن" + teacher name + contact + "الفهم قبل الحفظ". Completion: cover page complete.
5. **Add the mind map** (section 2): a simple text/shape diagram linking the lesson's main concepts. Completion: concept relationships visible.
6. **Add progressive content**: objectives → theory (framed paragraphs, bullets, side note boxes) → equations (each in its own shaded box with explanation + ⚠️ note) → tables (brand header) → experiments (boxed) → solved examples (boxed, step-by-step) → golden summary (5–7 points, gold tint) → exercises (with blank writing space + margin hint) → glossary (two-column table) → contacts. Completion: every lesson element present, in simple→complex order.
7. **Embed images** from `--images` where referenced. Completion: every image present.
8. **Add header/footer** on every page: header = lesson name + "مختبر الطيف للكيمياء"; footer = page number + "م. معتصم جادالله". Completion: both appear on every page.
9. **Self-check** against Verification. Completion: every checkbox satisfied.

## Pitfalls

- **RTL corruption:** Arabic must pass through `arabic_reshaper` then `bidi.algorithm.get_display` before insertion — never write raw Arabic, or letters render disconnected/reversed. Also set the section `rtl` and right alignment.
- **Equation rendering:** matplotlib mathtext needs LaTeX-valid syntax (`→` = `\rightarrow`, `⇌` = `\rightleftharpoons`). Validate each.
- **Full content, no summary:** Word is the complete reference — do not abridge (differs from the lab's brief boxes and the slides' brevity).
- **Brand uniformity:** same colors, fonts, logo, teacher name as steps 03–05.
- **Progression:** enforce simple→complex per `references/template.md`; don't dump everything in one block.
- **Editable requirement:** produce a real `.docx` (python-docx), not a flattened image.
- **Writing space:** exercises must leave blank room for student answers.
- **Header/footer:** both must appear on every page via section header/footer, not just the cover.

## Verification

- [ ] Every paragraph from the lesson is in the file.
- [ ] Every equation is clear and formatted.
- [ ] Every image is embedded and visible.
- [ ] Every solved example is step-by-step.
- [ ] Progression is clear (intro → definition → details → application → depth → self-assessment).
- [ ] Note/warning/success boxes are distinct.
- [ ] Tables are styled with brand colors.
- [ ] Exercises include blank writing space.
- [ ] The glossary is present.
- [ ] Logo and teacher name on cover and footer.
- [ ] The file opens and is editable in Word, A4 print-ready.
