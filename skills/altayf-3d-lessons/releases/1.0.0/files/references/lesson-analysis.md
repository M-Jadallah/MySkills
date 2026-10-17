# Lesson Analysis & Pedagogy

## Extracting the PDF

1. Read the attached PDF (converted to markdown by the reader). If pages render poorly, also read the PDF as images to catch figures, structures, and tables.
2. Build an inventory before writing anything:
   - **Objectives** (الأهداف) — usually at the lesson start.
   - **Concepts & definitions** — every defined term.
   - **Laws / equations / relationships** — each becomes a slider-driven interactive candidate.
   - **Structures & models** (crystals, molecules, orbitals, lattices) — each becomes a stage-structure candidate.
   - **Worked examples & numbers** — keep exact values.
   - **Tables & comparisons** — rebuild as `.table-wrap` tables.
   - **Figures** (الشكل N) — recreate the important ones as structures; cite the figure number in the card text like the reference does («الشكل 14»).
   - **End-of-lesson questions** — seed of the quiz + review grid.
3. If the PDF contains several lessons, treat each lesson as a top-level part with its own numbered sections on the same page.

## Completeness rule

Every fact, definition, example, and question in the PDF must appear in the final site. Compress the wording, never the content. After writing, re-scan the PDF inventory and check off each item.

## Gradual pedagogy per section

For each concept section (`.content-section` → `.lesson-card`), write in this order:

1. **Title + intro** — `h2` with cyan `<em>` accent + `.section-intro`: the full explanation, key terms bold.
2. **Concept cards** — `.concept-grid.three`: one card per sub-idea with a glyph icon (formula or symbol).
3. **Interaction panel** — if the concept has variables/structures: sliders/segmented controls bound to the stage + `.evidence-strip` (3 live facts) + `.model-note` («تحقق علمي:» invariant that updates with the controls). Tell the student what to do («سخّن المادة وراقب…»).
4. **Science pair / table** — comparisons as `.formula-card`/`.fact-card` pairs; big comparisons as `.table-wrap`.
5. **Worked examples** — the lesson's own examples in `.worked-example` collapsibles, with المعطيات والحل exactly.
6. **أتحقق** — the lesson's inline check questions in `.check-card` with `<details>` answers.
7. Optional: `.enrich-note` for enrichment alerts, `.life-link` for real-life applications from the lesson.

## Assessment section (always last)

- **Quiz** — 5–10 radio questions from the lesson's review questions: `fieldset[data-answer]` + `initQuiz` with one-line explanations per question.
- **Review grid** — the lesson's remaining review questions as `.review-grid` `<details>` Q&A.
- **Presets** — when the lesson has classify/compute examples, offer `.preset` chips that load those exact cases into the panel (reference: «المثال 11 - أ»).

## Language

- Arabic الفصحى المبسطة, tone of a caring expert teacher.
- Section tags bilingual: Arabic UI + small English tag pill (e.g. `Ionic Solids`).
- Chemistry terms in Arabic with formula/English on first use; numbers and formulas always `dir="ltr"`.
