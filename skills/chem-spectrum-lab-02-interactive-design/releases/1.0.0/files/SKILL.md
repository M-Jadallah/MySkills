---
name: chem-spectrum-lab-02-interactive-design
description: Design interactive 3D lab concepts (mandating 3D helper skills) from lesson Markdown.
version: 0.2.0
author: Mutja, Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [chem-spectrum-lab, interactive, 3d, design, tawjihi, r3f]
    related_skills: [chem-spectrum-lab-01-pdf-to-md, chem-spectrum-lab-03-lab-build, threejs-graphics-skills, altayf-3d-lessons]
---

# Chem Spectrum Lab — Step 02: Interactive & 3D Design Brief

Reads the canonical lesson Markdown from **step 01** and produces a bold, open-ended
**interactive 3D design brief** — the "brain" of the project. It maps every lesson
element to a concrete interactive 3D-lab experience, and — **mandatorily** — it plans
the build using **3D helper skills** so the later build (step 03, React Three Fiber)
is gorgeous and not a flat Canvas hack.

> ⚠️ **MANDATORY RULE** — this design MUST plan for *real* 3D (WebGL via React Three
> Fiber), not Canvas 2D. The brief MUST name which 3D helper capability each scene
> uses (from `threejs-graphics-skills` / `@react-three/drei` / `@react-three/postprocessing`).
> A design that says "draw with Canvas" or omits the 3D-helpers plan is INVALID.

## When to Use

- You have `lesson-XX.md` from `chem-spectrum-lab-01-pdf-to-md` and want the design plan.
- This is **step 02** of the `chem-spectrum-lab` pipeline — run it after step 01.
- Don't use for: building/implementing (that's step 03), or non-design tasks.

## 3D Helper Skills (MANDATORY to consult & cite)

Before writing the brief, you MUST load and use these helpers:

- **`threejs-graphics-skills`** (installed at `~/AppData/Local/hermes/skills/threejs-graphics-skills/`)
  — the vocabulary of sophisticated graphics. For each scene, pick the relevant
  capability: `threejs-procedural-materials` (PBR glass/liquid), `threejs-bloom`
  (glow), `threejs-procedural-vfx` (particles/smoke), `threejs-water-optics` (fluid),
  `threejs-volumetric-clouds`, `threejs-shadow-systems`, `threejs-exposure-color-grading`.
- **`@react-three/drei`** — `OrbitControls`, `Environment`, `Float`, `Sparkles`,
  `MeshTransmissionMaterial` (glass), `Html` (labels), `Bounds`.
- **`@react-three/postprocessing`** — `Bloom`, `Vignette`, `ChromaticAberration`, `DepthOfField`.
- Optionally **`altayf-3d-lessons`** for a reference landing-page pattern (same brand).

Cite the chosen helper in every row of the content→interaction map (see template §2).

## How to Run

1. Read `lesson-XX.md` with `read_file`.
2. Load the 3D helpers above (`skill_view` / read their SKILL.md) to internalize the
   available visual vocabulary.
3. Write the brief to `<lesson_dir>/design-XX.md` using `references/template.md`.
4. **Section 9 (Mandatory 3D-Plan)** MUST contain: a per-scene table of
   (scene → 3D helper used → effect → mobile tier), and the overall animation tier
   (epic on desktop / lean on mobile via `device.js`).

## Quick Reference

- Source: `lesson-XX.md` → Output: `design-XX.md`
- Every element must be mapped AND tagged with its 3D helper.
- Principles: understanding before memorizing, experience first, full control,
  visual realism (real 3D, not fake), gradual progression.

## Procedure

1. **Inventory the lesson** — list every element (theory, equations `$$...$$`,
   images, tables, examples, experiments, exercises). Completion: flat checklist.
2. **Write the lab vision** (§1) — atmosphere, tools, core 3D mechanism (drag piston /
   rotate molecule / tap atom). Completion: vivid scene targetable by the build.
3. **Load & cite 3D helpers** — for each planned scene, name the helper capability
   (e.g. "بويل cylinder → `MeshTransmissionMaterial` + `threejs-bloom`"). Completion:
   no scene is left without a named 3D helper.
4. **Build content→interaction map** (§2) — one row per element: interactive idea,
   interaction type, **3D helper used**, notes. Completion: exhaustive + helper-tagged.
5. **Detail experiments** (§3) — objective, steps, response, graph, **visual effects
   (glow/smoke/particles via helpers)**, sound. Completion: teaches "why."
6. **Define 3D visuals** (§4) — molecule rendering (balls-sticks/space-filling,
   rotatable), lab tools, lighting (PBR), camera rig (orbit/chase). Completion:
   consistent 3D language.
7. **Controls & navigation** (§5) — entry, stage movement, assistant, completion signal.
8. **Feedback & assessment** (§6) — in-experience checks, retry/hint, points.
9. **Inline brief** (§7) — 2–3 lines, appears AFTER action, hideable.
10. **Mobile plan** (§8) — per-experience phone adaptation; tier (epic/lean).
11. **⚠️ Mandatory 3D-Plan** (§9) — execution plan table + animation tiers. Completion:
    every scene has helper + effect + mobile tier; overall tier strategy stated.
12. **Self-check** against Verification.

## Pitfalls

- **Canvas 2D / no-3D:** INVALID. Must plan real WebGL 3D via R3F + helpers.
- **Helper not cited:** every scene MUST name its 3D helper capability.
- **Premature code:** describe *what/why*, not framework internals (but DO name helpers).
- **Unmapped elements:** table must be exhaustive.
- **Explanation-before-action:** brief appears AFTER interaction.
- **Desktop-only:** every idea explicitly mobile-feasible (lean tier).
- **No "why":** each experiment answers "لماذا".

## Verification

- [ ] Every lesson element mapped AND tagged with a 3D helper.
- [ ] §9 Mandatory 3D-Plan present: per-scene table + mobile tiers + overall strategy.
- [ ] Uses real 3D (R3F/drei/postprocessing), NOT Canvas 2D.
- [ ] Experiments teach "why."
- [ ] Inline brief ≤ 2–3 lines, shows after action.
- [ ] Mobile compatibility + tier stated for every idea.
- [ ] Output is `design-XX.md` following `references/template.md`.
