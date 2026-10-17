---
name: altayf-3d-lessons
description: "Build a complete interactive 3D lesson landing page from an attached chemistry lesson PDF (Tawjihi Jordan curriculum), branded for دوسية الطيف في الكيمياء — المهندس معتصم جادالله. Triggers when the user attaches a chemistry lesson PDF (درس كيمياء، توجيهي الأردن، الطيف في الكيمياء) and asks for an interactive 3D lesson page/site (موقع تفاعلي، صفحة هبوط ثلاثية الأبعاد، 3D lesson site) deployable to Coolify via Docker Compose. The skill deeply analyzes the PDF, writes a gradual Arabic explanation with zero information loss, renders parameter-driven pseudo-3D crystal/molecule simulations on a single adaptive stage with sliders, adds HUD, stats bar, interactive quiz, verifies rendering responsively, and outputs a Docker-ready zero-dependency project."
---

# Al-Tayf 3D Chemistry Lessons

Convert an attached chemistry lesson PDF into a polished, responsive Arabic (RTL) **landing page** whose hero and sticky sidebar host ONE live pseudo-3D stage that morphs as the student scrolls and moves sliders — delivered as a zero-dependency Docker-ready project for Coolify.

Fixed branding everywhere: **دوسية الطيف في الكيمياء — المهندس معتصم جادالله** (topbar brand + locked footer «إعداد وتقديم: المهندس معتصم جادالله»).

## Workflow

1. **Analyze the PDF** — Read `references/lesson-analysis.md`, then extract the full lesson structure (objectives, concepts, laws/equations, examples, tables, figures, end-of-lesson questions). Nothing in the PDF may be dropped. Multiple lessons in one PDF → numbered sections on the same page.

2. **Plan the landing page** — For each concept decide its section, semantic accent color, concept cards, and stage structure. Rules: any structure/model in the lesson becomes a stage structure; any law/variable becomes a slider or segmented control in that section's `.interaction-panel`; memorization facts become cards/tables.

3. **Scaffold from the template** — Copy `assets/template/` into `/mnt/agents/output/app`. The template ships: landing-page skeleton (topbar, progress bar, hero + stage shell, sticky stage, rail, locked footer), the full design CSS, the fixed engine (`js/engine.js` — never edit it), and a documented `js/app.js` skeleton. Fill placeholders with real lesson content. For a complete proven example of a finished lesson, study `assets/example-solid-state/` (index.html + app.js) and imitate its patterns.

4. **Apply the design system** — Follow `references/design-system.md`: light paper theme + dark navy hero/stage, semantic accent per section, the exact component classes (lesson-card, concept-grid, interaction-panel, evidence-strip, science-pair, check-card, worked-example, quiz, review-grid).

5. **Build the stage wiring** — Follow `references/stage-engine.md`. In `js/app.js`: register custom structures/palettes (or reuse the 10 stock structures), map sections → structures, bind every slider/segmented/strike control so the 3D model responds live, keep HUD + aria-live summary in sync. Physical fidelity matters: vibration amplitude ∝ √T(K), melting frees particles, ionic neutrality, electron-sea conservation.

6. **Write the explanation** — Gradual Arabic pedagogy per section (intro → concept cards → interactive → examples → أتحقق). All lesson information must appear; compress wording, never content. Generate glyph icons matching each topic.

7. **Assessment section** — Quiz (radio fieldsets + instant feedback + explanations + score + reset) from the lesson's own questions, plus a `.review-grid` of the remaining review questions. Hero stat grid shows real counts: المحاور، المحاكيات، الأسئلة.

8. **Verify before delivery** — Serve the site, then in a browser (headless Chromium is fine): screenshot at 390px, 768px, 1440px; run `stage.debug()` in console and require `chargeNeutral`, `electronCountConserved`, `atomsWithinExpectedAmplitude`, `atomsInsideWorldBounds`, `consoleErrors:0`, single loop. Drag the stage, move every slider, strike, melt, collapse/expand the mobile stage, grade the quiz. Fix and re-check.

9. **Package for Coolify** — `Dockerfile`, `docker-compose.yml`, `nginx.conf` ship with the template (see `references/deployment.md`). Zero runtime dependencies — no CDN, no vendoring. Deliver the project folder ready to push to the user's Git repo.

## Hard requirements

- Arabic RTL landing page; exact brand/footers from the template; semantic accent per section.
- ONE adaptive 3D stage (hero → sticky on scroll, collapsible on mobile) — never separate canvases per section.
- Every concept with variables gets live controls that visibly transform the model; every structure keeps physical invariants.
- Calm premium motion: smooth morphs, slow rotation, motion-pause toggle, `prefers-reduced-motion` honored.
- Works beautifully on phone/tablet/desktop — verify all three widths.
- Zero information loss from the PDF.
- Zero external dependencies (no CDN scripts/fonts); Docker-ready with `/health.json` healthcheck (Coolify rejects unhealthy containers).

## References

- `references/lesson-analysis.md` — PDF dissection + pedagogy + quiz construction. Read at step 1.
- `references/design-system.md` — palette, landing anatomy, component catalog. Read at step 4.
- `references/stage-engine.md` — engine API, stock structures, physics patterns, verification. Read at step 5.
- `references/deployment.md` — Docker/nginx/Coolify. Read at step 9.
- `assets/example-solid-state/` — complete proven lesson (الحالة الصلبة): imitate its HTML/app.js patterns.
