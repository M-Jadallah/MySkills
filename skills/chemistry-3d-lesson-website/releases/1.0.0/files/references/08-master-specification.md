# Canonical Expanded Specification

This reference preserves the complete intent of the original master prompt. `SKILL.md` defines the execution flow; this file supplies the expanded acceptance criteria.

## 1. Mission

Transform an uploaded chemistry lesson into a complete, premium, Arabic interactive website. The project must be suitable for Tawjihi self-study and classroom teaching. It must combine accurate explanation, guided examples, meaningful 3D scientific models, live controls, assessment, responsive behavior, offline delivery, and evidence-based testing.

The agent must not stop at a plan, wireframe, mockup, or first working prototype.

## 2. Source handling

- The lesson file is the scientific and curriculum source.
- The latest approved project is the visual, interaction, responsive, and architectural reference.
- The latest standalone HTML is the final-behavior and offline reference.
- Brand assets are authoritative for logos and identity graphics.
- Inspect rendered pages and embedded visuals; do not rely only on parsed text.
- Correct demonstrable scientific errors and document them.

## 3. Lesson coverage

Capture the complete lesson:

- main idea and outcomes;
- definitions and terminology;
- laws and equations;
- symbols, constants, assumptions, and units;
- variable relationships;
- microscopic explanations;
- experiments and apparatus;
- diagrams, tables, charts, and captions;
- worked examples;
- verification activities;
- review and multiple-choice questions;
- applications and misconceptions.

No major concept may be silently omitted.

## 4. Section design

Each major section should include when relevant:

1. title and objective;
2. concise introduction;
3. scientific explanation;
4. diagram or visual explanation;
5. interactive 3D model;
6. live controls and values;
7. equation and variable definitions;
8. changing and constant quantities;
9. **التحقق العلمي** card;
10. conclusion;
11. worked example;
12. quick check;
13. common mistake;
14. transition to the next section.

Use progressive disclosure and controlled visual variety.

## 5. Branding and footer

Preserve **الطيف في الكيمياء** and the approved footer. Do not redesign, translate, reorder, shorten, or replace footer content. Use the reference project as the design system. If absent, use the documented fallback navy/blue/cyan palette and disclose that exact footer preservation was impossible.

## 6. Arabic and notation

- Full RTL interface.
- Isolated LTR equation and chemical-formula containers.
- Correct fractions, subscripts, superscripts, units, decimals, signs, and parentheses.
- No hidden bidi controls or replacement-glyph squares.
- No malformed OCR text.
- Local equation rendering in the offline build.

## 7. Scientific 3D

Every scene must have a documented scientific purpose. Valid mappings include particle speed, density, collision rate, geometry, concentration, molecular angle, reaction progress, gauge values, container dimensions, or relative composition.

The scene must state its limitations. Representative particles must not be presented as literal molecular counts.

## 8. Continuous interaction

- One persistent renderer and render loop per active architecture.
- Scene initialization must not run from slider events.
- Input updates target state; visual state approaches it smoothly.
- Same canvas, same camera, and continuous particle trajectories during normal interaction.
- No refresh, flicker, blank frame, or duplicate event processing.
- Renderer resize only when actual dimensions change.

## 9. Desktop

Desktop must be suitable for teaching, with clear navigation, progress, readable content, a large simulation view, direct access to sections, full-screen mode, pause/resume, and reset. It must not be an enlarged mobile layout.

## 10. Mobile

Mobile must be designed intentionally:

- 360-430 px support;
- no page-level horizontal overflow;
- large touch targets and comfortable sliders;
- collapsible navigation;
- expandable simulation;
- optional bottom navigation;
- safe-area padding;
- portrait and landscape support;
- preserved simulation state during layout changes;
- adaptive performance without changing scientific meaning.

## 11. Examples and assessment

Worked examples must show data, target, law selection, unit conversion, substitution, calculation, result, unit, and reasonableness check. Solutions may reveal progressively.

Assessment must be based on the lesson and may include multiple choice, matching, prediction, numerical work, simulation interpretation, and true/false with explanation. Validate every answer and scoring rule.

## 12. Accessibility

Use semantic HTML, logical headings, visible focus, keyboard operation, accessible names, Arabic alt text, adequate contrast, reduced-motion support, pause controls, non-color feedback, and textual summaries of current simulation states.

## 13. Offline delivery

Provide both a maintainable source project and a direct-open standalone HTML. Bundle all required code, styles, icons, equation rendering, images, and assets locally. Do not depend on CDNs, remote APIs, analytics, or external font services.

## 14. Performance

Avoid scene reconstruction, excessive DOM updates, repeated long tasks, unnecessary transparency, and heavy offscreen rendering. Adapt visual complexity on mobile. Detect duplicate animation loops, listeners, observers, and persistent GPU-resource leaks.

## 15. Testing

Execute real tests on the actual output:

- independent scientific oracle;
- equations, units, constants, and examples;
- invariants;
- minimum, midpoint, maximum, intermediate, random, and invalid states;
- control-to-effect mapping;
- visual/numerical agreement;
- canvas persistence and no-refresh regression;
- frame continuity;
- end-to-end user journeys;
- desktop and mobile viewports;
- RTL and mixed text;
- accessibility;
- performance and memory;
- console and network audits;
- offline direct-file operation;
- WebGL and reduced-motion fallbacks;
- footer fingerprint.

If a test cannot run, mark it unexecuted and explain why. Never fabricate counts.

## 16. Code quality

Require linting, formatting, type checking where applicable, modular responsibilities, clear names, no dead code, no duplicate loops/listeners, no accidental globals, no obsolete commented code, no broken paths, no debug leftovers, and no remote dependencies in the offline build.

## 17. Required evidence

Deliver source, standalone HTML, ZIP, Arabic README, content and interaction maps, scientific and technical reports, test logs, screenshots for desktop/mobile/simulations, corrections, and exact final release counts.

## 18. Definition of done

The project is complete only when science, controls, visual behavior, desktop, mobile, offline output, locked footer, accessibility, and release reports pass the mandatory gate. Visual polish cannot hide an unresolved scientific or functional defect.
