---
name: chem-spectrum-lab-05-powerpoint
description: Build teaching PPTX and print PDF from lesson Markdown.
version: 0.1.0
author: Mutja, Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [chem-spectrum-lab, powerpoint, pptx, pdf, tawjihi]
    related_skills: []
---

# Chem Spectrum Lab — Step 05: PowerPoint & Print PDF

Reads the comprehensive lesson Markdown from **step 01** and produces two teaching artifacts: a fully editable `.pptx` presentation with tasteful animations (for class/recap), and a print-ready `.pdf` (A4 landscape, no animations) for students who want a hard copy. Unlike the lab, slides carry the *full theoretical explanation* — every paragraph, equation, image, table, solved example, experiment, and exercise. Same "مختبر الطيف" brand identity on every slide.

## When to Use

- You have a `lesson-XX.md` from `chem-spectrum-lab-01-pdf-to-md` and want a slide deck + print PDF.
- This is **step 05** of the `chem-spectrum-lab` pipeline — independent of steps 02–04 (works straight from the step-01 source).
- Don't use for: the interactive lab (steps 02–04) or PDF→Markdown extraction (step 01).

## Prerequisites

- The step-01 output `lesson-XX.md`.
- Python 3.11+ with: `pip install python-pptx matplotlib reportlab arabic-reshaper python-bidi`.
- The lesson's extracted images (from step 01, in `images/`) for embedding.

## How to Run

```bash
python "C:/Users/mutja/AppData/Local/hermes/skills/chem-spectrum-lab-05-powerpoint/scripts/build_pptx.py" \
  --lesson "<path>/lesson-XX.md" \
  --images "<lesson_dir>/images" \
  --out "<lesson_dir>"
```

This writes `<lesson_dir>/lesson-XX.pptx` (with animations) and `<lesson_dir>/lesson-XX-print.pdf` (no animations). Equations are rendered as PNG via matplotlib (Cambria Math style) and embedded; Arabic text is reshaped/reordered for RTL.

## Quick Reference

- Build: `terminal` → `build_pptx.py --lesson <md> --images <dir> --out <dir>`
- Slide structure spec: `read_file` `references/template.md`
- Brand colors/logo/teacher: `references/brand.md` (mirrors steps 03–04)
- RTL: handled inside the script via `arabic_reshaper` + `bidi.algorithm`; never hand-flip text.
- Two outputs: `.pptx` (animations) and `.pdf` (print, no animations).

## Procedure

1. **Confirm deps** (`python -c "import pptx, matplotlib, reportlab, arabic_reshaper, bidi"`). Completion: import succeeds.
2. **Parse `lesson-XX.md`** into sections: cover (title), objectives, intro, theory paragraphs, equations, tables, examples, experiments, exercises, closing. Completion: every `##`/`###` heading maps to a slide set.
3. **Build the `.pptx`** with python-pptx: 16:9, brand colors, logo + teacher name on every slide, RTL frames. Add animations per `references/template.md` (title Fade In, bullets Appear one-by-one, images Zoom In, equations Wipe left, tables Fade In). No slide transitions, no Morph, no video. Completion: file opens in PowerPoint and is editable.
4. **Render equations** to PNG with matplotlib using `amssymb`/serif (Cambria Math feel) and embed them as pictures. Completion: every `$$...$$` appears as a crisp image, balanced.
5. **Embed images** from `--images` where the Markdown references them. Completion: every image in the lesson appears on its slide.
6. **Build the print `.pdf`** with reportlab: A4 landscape, 2cm margins, same colors (or grayscale if needed), all text/images/tables, NO animations. Completion: PDF is a faithful static copy of the deck.
7. **Self-check** against Verification. Completion: every checkbox satisfied.

## Pitfalls

- **RTL corruption:** Arabic must be passed through `arabic_reshaper` then `bidi.algorithm.get_display` before placing in pptx/reportlab — never write raw Arabic into a shape, or letters render disconnected/reversed.
- **Equation rendering:** matplotlib's mathtext needs `$$...$$` with LaTeX-valid syntax; `→` is `\rightarrow`, `⇌` is `\rightleftharpoons`. Validate each before embedding.
- **Two distinct outputs:** the `.pptx` has animations; the `.pdf` must have NONE. Don't share the animated file as the print version.
- **Full explanation, no summary:** slides cover the complete theory — do not abridge (this differs from the lab's brief boxes).
- **Brand uniformity:** same colors, fonts, logo, and teacher name as steps 03–04.
- **Editable requirement:** produce a real `.pptx` (python-pptx), not a flattened image deck.
- **No complex animations:** banned list = Morph, slide transitions, embedded video.

## Verification

- [ ] Every paragraph from the lesson is in the slides.
- [ ] Every equation is rendered clearly (PNG, balanced, Cambria-Math style).
- [ ] Every image is embedded and visible.
- [ ] Every solved example is step-by-step.
- [ ] Logo and teacher name appear on every slide.
- [ ] The presentation `.pptx` contains the specified animations.
- [ ] The print `.pdf` has no animations.
- [ ] The `.pptx` opens and is editable in PowerPoint.
