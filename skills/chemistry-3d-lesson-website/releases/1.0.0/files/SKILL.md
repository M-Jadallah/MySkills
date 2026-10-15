---
name: chemistry-3d-lesson-website
description: Convert an uploaded chemistry lesson and an approved reference project into a complete Arabic RTL interactive educational website with scientifically accurate 3D simulations, polished desktop/mobile layouts, the locked "الطيف في الكيمياء" identity and footer, continuous no-refresh controls, offline standalone delivery, and a mandatory evidence-based release gate.
version: 1.0.0
---

# Chemistry 3D Lesson Website Skill

Use this skill when an agent must transform a chemistry lesson file into a premium, production-ready, Arabic interactive website for study and classroom teaching.

The skill is not satisfied by a plan, prototype, mockup, or decorative animation. The agent must analyze, build, test, repair, retest, package, and deliver a complete working project.

## Activation criteria

Activate this skill when the user provides one or more of the following:

- a chemistry lesson PDF, DOCX, PPTX, scan, or image set;
- a previously approved interactive chemistry website;
- branding assets for **الطيف في الكيمياء**;
- a request for 3D scientific simulations, responsive desktop/mobile design, RTL Arabic, or offline delivery;
- a request to reproduce the quality and behavior of the approved reference project for a new lesson.

Do not activate for a simple summary, static worksheet, ordinary article, or a request that does not require an interactive website.

## Required inputs

The preferred input bundle is:

1. **Lesson file** - the scientific and educational source of truth.
2. **Latest reference project ZIP or source folder** - the visual, responsive, interaction, and technical reference.
3. **Latest standalone reference HTML** - the approved final behavior and offline reference.
4. **Optional brand assets** - logos, teacher image, icons, fonts, and approved identity elements.

When multiple reference versions are provided, identify and use the latest approved version. Do not mix obsolete implementations into the final project.

## Non-negotiable requirements

The final project must:

- be fully Arabic and RTL, while equations and chemical notation remain correctly LTR;
- preserve the approved **الطيف في الكيمياء** identity;
- preserve the approved footer exactly;
- include meaningful scientific 3D visualizations rather than decorative particles;
- update controls continuously without page refresh, canvas replacement, renderer recreation, or scene reinitialization;
- provide a deliberately designed desktop experience and a deliberately designed mobile experience;
- work offline as a standalone HTML file;
- include independent scientific validation, functional tests, responsive tests, accessibility checks, performance checks, and code-quality checks;
- disclose any test that could not be executed;
- pass the release gate before delivery.

## Skill package map

- `references/01-input-contract.md` - required files, precedence rules, and reference-project handling.
- `references/02-lesson-analysis.md` - deep content extraction and lesson-mapping workflow.
- `references/03-design-and-rtl.md` - visual identity, desktop/mobile design, Arabic RTL, equations, and footer lock.
- `references/04-scientific-simulations.md` - scientific modeling, 3D mapping, real-time architecture, and visual limitations.
- `references/05-testing-release-gate.md` - mandatory scientific, browser, responsive, performance, accessibility, and offline tests.
- `references/06-delivery-contract.md` - required deliverables, reports, screenshots, and final response format.
- `references/07-testability-contract.md` - required DOM attributes and debug instrumentation for automated testing.
- `references/08-master-specification.md` - canonical expanded acceptance criteria preserving the full master prompt.
- `templates/` - configuration, schemas, report templates, and footer-lock markers.
- `scripts/` - project initialization, input inventory, RTL scan, offline audit, map validation, footer verification, quality-gate runner, and release packaging.
- `browser-tests/` - Playwright regression suite for canvas persistence, controls, overflow, assets, console errors, and footer lock.
- `examples/gas-state/` - compact example maps and an independent gas-law oracle.

## Mandatory workflow

### Phase 1 - Inspect and inventory

1. Inventory every uploaded file.
2. Compute file hashes and record sizes and extensions.
3. Identify the lesson source, latest reference project, standalone reference HTML, and brand assets.
4. Inspect visual pages, not only parsed text.
5. Identify the approved footer and save a locked copy or fingerprint.

Recommended command:

```bash
python scripts/inspect_inputs.py \
  --lesson /path/to/lesson.pdf \
  --reference-project /path/to/reference-project \
  --reference-html /path/to/reference.html \
  --brand-assets /path/to/brand-assets \
  --output reports/input-inventory
```

### Phase 2 - Analyze the lesson

Follow `references/02-lesson-analysis.md`.

Create:

- `lesson-content-map.json`
- `interaction-map.json`
- `source-corrections.md`

Validate the maps:

```bash
python scripts/validate_maps.py \
  --content-map lesson-content-map.json \
  --interaction-map interaction-map.json
```

Do not start implementation until the lesson map covers every major concept, equation, example, experiment, visual, review question, and misconception.

### Phase 3 - Define the scientific models

For every interactive section, document:

- controlled variables;
- dependent variables;
- constants;
- valid ranges;
- units;
- governing equation;
- independent scientific oracle;
- visual mapping;
- scientific invariant;
- limitations of the representative model;
- reset state.

Use a separate scientific oracle. Never validate production calculations by calling the same production function.

### Phase 4 - Implement the project

Use a maintainable modular architecture. Separate:

- lesson content;
- equations and unit conversions;
- scientific state;
- target visual state;
- current interpolated visual state;
- 3D scene controllers;
- UI controls;
- navigation;
- responsive behavior;
- examples and assessment;
- accessibility;
- tests.

Initialize each 3D scene once. Maintain a persistent render loop. Input events update state only.

### Phase 5 - Apply the design system

Follow `references/03-design-and-rtl.md`.

Preserve:

- the **الطيف في الكيمياء** palette and visual language;
- the approved desktop layout quality;
- the approved mobile interaction quality;
- the footer exactly.

Do not simply replace text inside the old page. Build new simulations and interactions that fit the new lesson.

### Phase 6 - Build for testability

Follow `references/07-testability-contract.md`.

Required examples:

```html
<section data-lesson-section="boyle-law">...</section>
<div data-science-sim="boyle-law">...</div>
<canvas data-simulation-canvas="boyle-law"></canvas>
<input data-control-id="pressure" data-scientific-variable="P" type="range">
<div data-verification-card="boyle-law">...</div>
```

Expose non-production debug counters during tests:

```js
window.__SCIENCE_DEBUG__ = {
  sceneInitCount: {},
  rendererCreateCount: {},
  activeAnimationLoops: 0,
};
```

### Phase 7 - Test, repair, and retest

Follow `references/05-testing-release-gate.md` completely.

The first working build is only a test candidate.

At minimum, execute:

- static code-quality checks;
- independent scientific oracle tests;
- dimensional and unit tests;
- invariant tests;
- randomized valid and invalid input tests;
- component and integration tests;
- Playwright end-to-end tests;
- no-refresh and canvas-persistence tests;
- responsive tests at all required viewports;
- visual inspection;
- RTL and mixed-text checks;
- accessibility checks;
- performance and memory stress tests;
- offline standalone-file tests;
- browser console and missing-asset audits.

Run the packaged static checks:

```bash
python scripts/run_quality_gate.py --config project-config.json
```

Run browser tests from `browser-tests/`:

```bash
npm install
npx playwright install chromium
TARGET_FILE=/absolute/path/to/standalone.html npm test
```

Every failure must enter a fix-retest loop:

1. Record the failure.
2. Identify the root cause.
3. Fix the root cause.
4. Add or update a regression test.
5. Rerun the failed test.
6. Rerun related tests.
7. Rerun the complete suite before release.

### Phase 8 - Audit offline behavior and RTL

Run:

```bash
python scripts/check_rtl_unicode.py --path dist --fail-on-found
python scripts/check_offline_assets.py --path dist --fail-on-remote --fail-on-missing
```

Do not use hidden bidi control characters to repair layout. Use structural HTML direction rules.

### Phase 9 - Verify the locked footer

Wrap the approved footer in the final HTML with:

```html
<!-- FOOTER_LOCK_START -->
...approved footer...
<!-- FOOTER_LOCK_END -->
```

Create a fingerprint from the approved reference footer:

```bash
python scripts/footer_lock.py fingerprint \
  --html approved-reference.html \
  --output templates/footer-lock.json
```

Verify the final output:

```bash
python scripts/footer_lock.py verify \
  --html dist/lesson-standalone.html \
  --lock templates/footer-lock.json
```

### Phase 10 - Package the release

Only after the release gate passes:

```bash
python scripts/package_release.py \
  --project-root . \
  --output release/chemistry-lesson-project.zip \
  --config project-config.json
```

## Required deliverables

The agent must deliver:

1. Complete source-code folder.
2. Single offline standalone HTML file.
3. ZIP archive of the complete project.
4. Arabic README.
5. Lesson-content map.
6. Interaction/control map.
7. Scientific validation report.
8. Functional test report.
9. Responsive test report.
10. Accessibility report.
11. Performance report.
12. Code-quality report.
13. Source-correction report.
14. Test logs.
15. Desktop screenshots.
16. Mobile screenshots.
17. Major simulation screenshots.
18. Final release-gate summary with actual executed counts.

## Release gate

Do not declare completion unless all release-blocking conditions pass:

- lesson coverage is complete;
- equations, units, examples, and answer keys are validated;
- scientific invariants pass;
- visual models agree with numerical models;
- all controls work at minimum, midpoint, maximum, and randomized states;
- the same canvas remains mounted during input;
- renderer and scene initialization counts do not increase during slider movement;
- no unexpected particle reset occurs;
- desktop and mobile tests pass;
- no unexplained horizontal overflow remains;
- the standalone file works with network access disabled;
- the footer fingerprint matches;
- code-quality checks pass;
- no uncaught browser errors or missing required assets remain;
- all required reports exist.

Use actual executed test counts. Never fabricate impressive numbers.

## Failure honesty

If a required tool or environment is unavailable:

- state exactly which test was not executed;
- explain why;
- do not mark it as passed;
- perform the strongest available alternative;
- document the limitation in the final report.

If a release-blocking scientific or functional defect remains, do not describe the project as complete.

## Final response contract

The final response must include:

- links to all final files;
- exact scientific-test counts;
- exact unit and invariant-test counts;
- functional and end-to-end status;
- desktop and mobile status;
- accessibility status;
- performance status;
- code-quality status;
- offline standalone status;
- console-error count;
- missing-asset count;
- remaining limitations.

Avoid unsupported phrases such as "should work", "appears correct", or "fully tested" without evidence.
