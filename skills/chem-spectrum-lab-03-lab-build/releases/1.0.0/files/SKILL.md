---
name: chem-spectrum-lab-03-lab-build
description: Build standalone 3D chemistry lab (React Three Fiber) from design.
version: 0.2.0
author: Mutja, Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [chem-spectrum-lab, build, 3d, react-three-fiber, tawjihi]
    related_skills: [chem-spectrum-lab-02-interactive-design, chem-spectrum-lab-04-integration]
---

# Chem Spectrum Lab — Step 03: 3D Lab Build (React Three Fiber)

Takes the interactive design brief (`design-XX.md`) from **step 02** and builds a
real, runnable 3D lab using **React + React Three Fiber + Drei + postprocessing**
with the full "مختبر الطيف للكيمياء" brand identity. Bloom/Vignette postprocessing
gives the "wow" factor on desktop; on mobile the same scene runs with reduced
particle counts and disabled heavy effects via `shared/device.js` (tier check),
so 3D stays on every device without killing performance.

## When to Use

- You have a `design-XX.md` from `chem-spectrum-lab-02-interactive-design`.
- This is **step 03** of the `chem-spectrum-lab` pipeline — run it after step 02.
- Build a gorgeous, interactive 3D lab (molecules, piston, live gas-law physics).

## Tech Stack (approved)

- React 18 + TypeScript + Vite
- `@react-three/fiber` (R3F) — declarative Three.js
- `@react-three/drei` — OrbitControls, Environment, Float, Sparkles, MeshTransmissionMaterial
- `@react-three/postprocessing` — Bloom, Vignette (epic tier)
- `framer-motion` — UI transitions
- `zustand` — lab state store
- Docker: multi-stage (node build → nginx serve). See `references/docker/`.

## Prerequisites

- Node 20+ and npm. `node --version` succeeds.
- A `frontend/` Vite project (scaffold from this skill or the orchestrator).
- `npm install` of the dependencies above.

## How to Run

1. `cd frontend && npm install` — install deps. Completion: `node_modules` exists.
2. Implement the lab scene in `src/lab/` (GasScene.tsx + store.ts + ui/HUD.tsx) from
   `design-XX.md`. The scene must: render a glass cylinder with animated molecules,
   a draggable piston controlling volume, six gas-law tabs (Boyle/Charles/Gay-Lussac/
   Avogadro/Ideal/Dalton), live HUD readouts, and Bloom postprocessing on desktop.
   Completion: `npm run build` exits 0 and `dist/` is produced.
3. `npm run build` — production build. Completion: `dist/index.html` + assets exist.
4. `npm run preview` — verify it serves. Completion: `curl localhost:4173` returns HTML.
5. (Optional) `docker compose -f docker/docker-compose.yml build` — verify image builds.

## Pitfalls

- **Canvas 2D is deprecated for the lab** — the gorgeous 3D look requires R3F.
- **Mobile**: keep `device.js` tier check; reduce `Sparkles` count + skip Bloom on `lean`.
- **Bundle size**: R3F is ~350KB gzipped — acceptable; enable gzip in nginx.
- **SPA routing**: nginx must `try_files $uri /index.html` for deep links.

## Verification

- [ ] `npm run build` succeeds with no TypeScript errors.
- [ ] `dist/index.html` references the built JS/CSS.
- [ ] The 3D scene loads (WebGL canvas, molecules animate, piston responds).
- [ ] Six gas-law tabs switch the simulation.
- [ ] HUD shows live volume/pressure/temp/moles/score.
- [ ] Docker multi-stage build produces a working nginx image.
