---
name: chem-spectrum-lab-04-integration
description: Integrate single-lesson labs into the full lab site.
version: 0.1.0
author: Mutja, Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [chem-spectrum-lab, integration, website, tawjihi]
    related_skills: []
---

# Chem Spectrum Lab — Step 04: Integration

Takes the standalone single-lesson labs built in **step 03** and integrates them into one cohesive web app — the "مختبر الطيف للكيمياء" main site. It produces the main pages (home, about, contact, lessons list), the shared header/footer, a welcome/name screen, LocalStorage progress + dark/light theme, and prev/next lesson navigation. Lessons are added **one at a time, in Jordanian-book order**, with the teacher deciding each lesson's number and placement.

## When to Use

- You have one or more `frontend/lessons/lesson-XX/` labs from `chem-spectrum-lab-03-lab-build` and want the integrated site around them.
- This is **step 04** of the `chem-spectrum-lab` pipeline — run after step 03.
- Don't use for: building a single lesson's internals (that's step 03) or the PDF/design phases (steps 01–02).

## Prerequisites

- A `frontend/` repo root (may already contain `lessons/lesson-XX/` from step 03).
- `scaffold.py` (this skill's helper) needs only stdlib Python 3 — no pip installs.
- Brand constants: `read_file` `references/brand.md`.

## How to Run

1. **Initialize the site shell** (once):
   ```bash
   python "C:/Users/mutja/AppData/Local/hermes/skills/chem-spectrum-lab-04-integration/scripts/scaffold.py" \
     --init --root "<path>/frontend"
   ```
2. **Register a lesson** (each time the teacher adds one — never batch):
   ```bash
   python "C:/Users/mutja/AppData/Local/hermes/skills/chem-spectrum-lab-04-integration/scripts/scaffold.py" \
     --add-lesson XX --title "عنوان الدرس" --root "<path>/frontend"
   ```
   The teacher states the lesson number/placement; the tool inserts the card into `lessons.html` in book order and wires prev/next nav.
3. **Deploy** (optional): follow `references/deploy.md` (GitHub → Coolify → Docker Compose on VPS).

## Quick Reference

- Init shell: `terminal` → `scaffold.py --init --root <path>`
- Add lesson: `terminal` → `scaffold.py --add-lesson XX --title "..." --root <path>`
- Brand identity: `references/brand.md`
- Page structure + project tree: `references/template.md`
- Deploy steps: `references/deploy.md`
- Storage API contract: `shared/storage.js` (`ChemLabStorage`)
- Shared assets live in `frontend/shared/`; lesson labs reference them via `../../shared/`

## Procedure

1. **Initialize the shell** with `--init`. Completion: `index.html`, `about.html`, `contact.html`, `lessons.html`, `css/site.css`, `shared/{storage,layout,nav,lessons-data}.js`, `shared/theme.css`, and Docker files at repo root all exist.
2. **Confirm unified identity.** Every page loads the same header (logo + nav + theme toggle + student name) and footer (copyright + contact) via `shared/layout.js`. Completion: header/footer are byte-identical in markup across pages.
3. **Add lessons one at a time.** For each, run `--add-lesson XX --title "..."`. Completion: `shared/lessons-data.js` lists the lesson; `lessons.html` shows its card in book order with an "ادخل المختبر" button; the teacher's chosen number/position is honored.
4. **Wire the welcome screen.** `shared/layout.js` shows the name prompt on first visit, saves to LocalStorage, displays the name top-right, and supports "تخطي". Completion: name appears in the header after entry; skip leaves it blank.
5. **Wire storage + theme.** `shared/storage.js` implements the `ChemLabStorage` API (name, progress, theme, last lesson). Theme toggle flips dark/light and persists. Completion: toggling theme on any page persists across reloads.
6. **Wire prev/next + progress.** Inside each lesson lab, `shared/nav.js` provides previous/next buttons and a progress bar sourced from `lessons-data.js` and `ChemLabStorage`. Completion: navigating from one lesson reaches the adjacent one and marks completion.
7. **Deploy (optional).** Follow `references/deploy.md`. Completion: `docker compose build` succeeds and the site serves on :3000.
8. **Self-check** against Verification. Completion: every checkbox satisfied.

## Pitfalls

- **Batch addition:** never add more than one lesson per run. The teacher decides each lesson's number/placement; doing several at once risks wrong book order.
- **Book order:** cards must follow the Jordanian textbook order, not filesystem order. `--add-lesson` inserts by the teacher-stated number.
- **Unified identity:** header/footer must be identical everywhere — inject them via `shared/layout.js`, never copy-paste divergent markup.
- **LocalStorage now, API later:** the storage contract is LocalStorage only today; keep the API stable so a future backend swap (JWT/OAuth/Postgres) doesn't break callers.
- **Optional name:** the student may skip the name prompt; every page must still render without it.
- **Mobile:** the shell and every lesson must be usable at ≥360px; re-test after each lesson addition.
- **Docker reuse:** Docker files belong to step 03's first lesson; step 04 init only copies them if absent — don't duplicate config.

## Verification

- [ ] The lesson appears in `lessons.html` in the correct book order.
- [ ] Previous/next navigation works between lessons.
- [ ] LocalStorage saves progress (completed lessons marked).
- [ ] The student name appears top-right after entry (and skip works).
- [ ] Dark/light toggle works on every page and persists.
- [ ] Docker builds the whole project without errors.
- [ ] The site works on a phone-width viewport.
