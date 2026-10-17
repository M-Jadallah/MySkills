# Design System — الطيف في الكيمياء (v2)

Adopted verbatim from the user's approved reference implementation (`assets/example-solid-state/`). The template ships the exact CSS (`assets/template/styles.css`) — reuse its classes, never restyle from scratch. Add lesson-specific classes (icons, panel tints) in the same spirit.

## Palette

Light paper theme with a dark navy hero + 3D stage. Semantic accents identify each topic family.

```css
--navy-950:#041426; --navy-900:#061d35; --navy-800:#0a2a49; --navy-700:#0d3b61;
--blue:#1677c8;  --cyan:#22c7d8;  --cyan-soft:#dffaff;
--pink:#e74493;  --orange:#ff9b42; --green:#26b983; --purple:#8a5bd4;
--ink:#0b2742;   --muted:#52677a;  --line:#dbe7ef;
--paper:#f4f8fb; --white:#fff;
--radius-lg:28px; --radius-md:20px; --radius-sm:14px;
```

- Body: `--paper` background, `--ink` text, Tahoma/"Segoe UI" stack, line-height 1.8.
- Hero + stage: dark navy gradient (`#041426 → #072a49 → #061d35`) with radial cyan/purple glows and two fixed blurred ambient blobs (cyan + pink).
- Assign each lesson section ONE semantic accent: section-tag, panel tint, and concept-icon colors follow it (reference: properties=blue, molecular=purple, network=blue, metallic=orange, ionic=pink, identify=green).

## Landing-page anatomy (fixed order)

1. `.topbar` — fixed, blurred navy; brand mark (flask SVG) + «الطيف في الكيمياء» + subtitle «كيمياء التوجيهي - الثاني عشر الأكاديمي»; desktop nav; motion-pause and reset icon buttons. Gains shadow on scroll.
2. `.reading-progress` — 3px pink→cyan gradient bar tracking scroll.
3. `.hero` — full viewport; right: copy (eyebrow, huge `clamp(3.7rem,8vw,7.4rem)` title with cyan `<em>` accent, lead, actions, 3-stat grid); left: live 3D stage (slight `perspective` tilt).
4. `.lesson-layout` — grid: `.sticky-stage` (the SAME stage shell moves here after the hero) + `.lesson-content` sections. On mobile the stage becomes a 42vh sticky strip with a collapse toggle (طي المجسم).
5. `.section-rail` — fixed side dots with tooltips; active dot follows the visible section.
6. `.content-section`s → footer (locked brand + «إعداد وتقديم: المهندس معتصم جادالله»).

## The stage shell (`.stage-shell`)

Canvas wrapped by: `.stage-grid` (faint cyan blueprint grid), `.stage-vignette`, `.stage-hud` (kicker + title + metric chips), `.stage-bottom` (3 live metrics), `.canvas-hint` («اسحب لتدوير المشهد»), `.stage-tool` fullscreen button, and `.sr-only` aria-live summary (`#simSummary`). Every generated stage must keep all of these.

## Content components (use these exact classes)

- `.lesson-card` — white card, top gradient stripe, giant watermark `.section-number` (01, 02…), `.section-tag` (+ color variant: pink/green/blue/orange/purple), `h2` with cyan `<em>`, `.section-intro`.
- `.concept-grid.three` → `.concept-card` with glyph `.concept-icon` (define per-lesson glyphs with `::before` like the reference: `〰 ▣ °C I—I H···O C₆₀ ◇ ⬡ SiO₂ ⚡`).
- `.interaction-panel` (+ tint variant per section) — the control surface: `.interaction-heading` (kicker + title + `<output>` state), `.range-row` (slider + output), `.segmented` (2–3 buttons), `.evidence-strip` (3 fact cells), `.model-note` («تحقق علمي:» live-updating invariant), optional `.experiment-actions` (strike/restore buttons), `.preset-row` (`.preset` chips), `.toggle-grid`.
- `.science-pair` — `.formula-card` (dark navy gradient, LTR formulas) / `.fact-card` (+ `violet-card` / `blue-card`).
- `.table-wrap` — responsive table (`min-width:640px`, scrolls), formulas `dir=ltr`.
- `.check-card` — «أتحقق» question + `<details>` answer. `.worked-example` — collapsible solved example. `.enrich-note` — «تنبيه إثرائي». `.life-link` — real-life application band.
- Quiz: `<form class="quiz">` of `fieldset[data-answer]` + radio labels + `.quiz-feedback`; `.quiz-actions` with submit/reset/score `<output>`. `.review-grid` — `<details>` Q&A for lesson review questions.

## Motion & comfort

- `scroll-behavior:smooth`, 0.2s transitions on hover lifts (`translateY(-2/-3px)`), structure morphs ≈ 0.4s smoothstep inside the engine, slow drag rotation.
- Motion-pause toggle in the topbar (`body.motion-paused` freezes all animation) — mandatory.
- Full `prefers-reduced-motion` block already in the CSS — keep.
- No dense pages: sections ~95vh, cards breathe, one idea per card.

## Responsive breakpoints (already in CSS)

1180px (nav→burger, single-column grids) · 900px (stage becomes sticky strip, single-column hero) · 560px (stat grid stacks, segmented stacks, smaller stage). Touch targets ≥ 42px everywhere; mobile nav grid 2 columns.
