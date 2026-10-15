---
name: chem-spectrum-lab
description: Coordinate the chem lab pipeline (incl. 3D R3F lab) via sub-agents.
version: 0.2.0
author: Mutja, Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [chem-spectrum-lab, orchestrator, pipeline, tawjihi]
    related_skills: [chem-spectrum-lab-01-pdf-to-md, chem-spectrum-lab-02-interactive-design, chem-spectrum-lab-03-lab-build, chem-spectrum-lab-04-integration, chem-spectrum-lab-05-powerpoint, chem-spectrum-lab-06-word, threejs-graphics-skills]
---

# Chem Spectrum Lab — Orchestrator (Pipeline Coordinator)

One entry point that turns a single chemistry lesson PDF into the **entire** "مختبر الطيف للكيمياء" deliverable set: a canonical Markdown source, an interactive design brief, a standalone interactive lab, the integrated website, a teaching PPTX+PDF, and a Word study doc — then packages the web app for **Coolify deployment via Docker Compose with zero friction**. Each pipeline step runs in its own sub-agent so work proceeds in parallel where the dependency graph allows.

## When to Use

- User supplies ONE lesson PDF and wants the full lab ecosystem built end-to-end.
- This is the **orchestrator** for the `chem-spectrum-lab` pipeline — it drives steps 01–06, it is not one of them.
- Don't use for: a single isolated step (call that step's own skill directly), or anything outside the chem-lab pipeline.

## Prerequisites

- The lesson PDF path, and an agreed lesson number/book position from the teacher.
- The six step skills present locally: `chem-spectrum-lab-01-pdf-to-md` … `chem-spectrum-lab-06-word`.
- `pip install pymupdf python-pptx python-docx arabic-reshaper python-bidi matplotlib reportlab` for the sub-agents.
- A repo root `chem-spectrum-lab/` where `frontend/`, `docker/`, etc. live.

## How to Run

Invoke via `delegate_task` (sub-agents), following the Procedure's dependency-aware workflow. You (the orchestrator) stay in the loop, spawn agents per step, and assemble the final deployable tree. Each sub-agent is told which step-skill to load (`skill_view`) and given exact input/output paths.

## Quick Reference

- Steps & skills: 01 `chem-spectrum-lab-01-pdf-to-md`, 02 `chem-spectrum-lab-02-interactive-design`, 03 `chem-spectrum-lab-03-lab-build`, 04 `chem-spectrum-lab-04-integration`, 05 `chem-spectrum-lab-05-powerpoint`, 06 `chem-spectrum-lab-06-word`.
- Architecture & Docker: `read_file` `references/architecture.md` and `references/docker/*`.
- Animation guide (desktop-first, epic): `references/animation-guide.md`.
- Deploy target: Coolify → "Docker Compose" build pack → `docker/docker-compose.yml`.

## Procedure (dependency-aware workflow)

**Phase 0 — Setup.** Create the repo tree (`chem-spectrum-lab/{frontend,shared,docker,backend,database}`) from `references/architecture.md`. Decide lesson number `XX` with the teacher. Completion: tree + `XX` known.

**Phase 1 — Source (SEQUENTIAL, blocks everything).** Spawn ONE sub-agent running `chem-spectrum-lab-01-pdf-to-md` on the PDF → produces `frontend/lessons/lesson-XX/_src/lesson-XX.md` (the single source of truth). Completion: canonical Markdown exists. **Do not start steps 02–06 until this lands.**

**Phase 2 — Parallel fan-out (THREE agents at once).** Once `lesson-XX.md` exists, spawn three independent sub-agents in ONE `delegate_task(tasks=[...])` batch (they only read the step-01 source):
  - **Agent A (design):** `chem-spectrum-lab-02-interactive-design` → `design-XX.md`.
  - **Agent B (slides):** `chem-spectrum-lab-05-powerpoint` → `lesson-XX.pptx` + `lesson-XX-print.pdf`.
  - **Agent C (word):** `chem-spectrum-lab-06-word` → `lesson-XX.docx`.
  Completion: all three artifacts present.

**Phase 3 — Lab build + integration (SEQUENTIAL, depends on Agent A).** First spawn `chem-spectrum-lab-03-lab-build` (reads `design-XX.md`) → standalone lab at `frontend/lessons/lesson-XX/`. When that finishes, spawn `chem-spectrum-lab-04-integration` (`--add-lesson XX`) to register it in the integrated site. Completion: lab built + registered, header/footer/theme wired.

**Phase 4 — Animation hardening (desktop-first).** Instruct the step-03/04 agents (or a dedicated pass) to apply `references/animation-guide.md`: detect device, crank the **desktop** tier to the epic level (glow, particles, morph, screen transitions), keep mobile lean. Completion: `device.js` present and desktop effects verified.

**Phase 5 — Deploy package.** Copy `references/docker/*` into `chem-spectrum-lab/docker/`. Verify `docker compose config` is valid and the image builds (`docker compose build`). Completion: compose validates and builds.

**Phase 6 — Self-check** against Verification. Completion: every checkbox satisfied.

## Animation Policy (CRITICAL)

- **Desktop = epic.** On non-touch / wide viewports, default to the strongest tier in `references/animation-guide.md`: neon glow, particle Canvas, glassmorphism, screen-to-screen transitions, staggered reveals. This is the "wow" experience.
- **Mobile = lean.** On touch / narrow viewports, drop to the lightweight tier (simple fade/appear, no heavy particles, no WebGL) to protect framerate.
- Device detection is via `navigator.maxTouchPoints` + `matchMedia('(pointer:fine)')` + width — see `device.js` in the guide. Never hard-block animations on desktop to satisfy mobile; branch instead.

## Deployment Architecture (Coolify-safe)

The `docker/docker-compose.yml` uses a **build-based image** (Dockerfile `COPY`s `frontend/`), NOT a host volume mount — so Coolify's builder produces a self-contained image with no local-path dependency. nginx serves the SPA. Port maps `3000:80`. Secrets (if any backend later) go through env, never baked into the image. See `references/architecture.md` for the full tree and the "do / don't" deploy list.

## Pitfalls

- **Running 02–06 before 01 finishes:** they depend on the canonical Markdown. Gate them on Phase 1 completion.
- **Fan-out too early:** only 02/05/06 are parallel-safe; 03 needs 02's `design-XX.md`, and 04 needs 03's built lab. Keep 03→04 sequential.
- **Volume-mount compose for Coolify:** a `./frontend:/usr/share/nginx/html:ro` bind in production breaks on Coolify (no host path). Use the build-based Dockerfile in `references/docker/`.
- **One-shot lesson batching:** steps 03/04 add ONE lesson at a time (teacher sets number/position) — never loop several lessons in one agent run.
- **Desktop animation leaking to mobile:** branch by device; don't ship epic particles to phones.
- **Brand drift:** every step reuses `references/brand`-equivalent constants; the orchestrator must keep lesson number + teacher/contact identical across all outputs.

## Verification

- [ ] `lesson-XX.md` produced by step 01 before any downstream step started.
- [ ] `design-XX.md`, `lesson-XX.pptx`, `lesson-XX-print.pdf`, `lesson-XX.docx` all produced (phases 2–3).
- [ ] Standalone lab built at `frontend/lessons/lesson-XX/` and registered in the site.
- [ ] Desktop animations are at the epic tier; mobile is lean (verify `device.js` branching).
- [ ] `docker/docker-compose.yml` is build-based and `docker compose config` passes.
- [ ] `docker compose build` succeeds with no local-path dependency.
- [ ] All outputs share identical brand, teacher name, and contact numbers.
