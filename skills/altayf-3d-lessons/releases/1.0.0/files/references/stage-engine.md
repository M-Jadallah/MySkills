# Stage Engine — Authoring Guide

`assets/template/js/engine.js` is a dependency-free pseudo-3D engine (2D canvas + custom projection). ONE stage shell hosts ONE canvas; the structure morphs as the student scrolls and as controls change. Never edit engine.js per lesson — all lesson logic lives in `js/app.js`. Full proven example: `assets/example-solid-state/app.js`.

## Core concepts

- **Structures are data**: `{ atoms, bonds, coordination?, cage?, sea?, slip? }`. Atom: `{x, y, z, type, charge, size, layer?}` in world units (`WORLD = x:0.86, y:±0.78, z:0.68`). Bond: `{a, b, kind}` where kind ∈ `strong | covalent | hbond | weak | ionic`.
- **Persistent atom pool** (default 80): switching structures morphs atoms smoothly — the scene is initialized once. Keep structures ≤ `maxAtoms`.
- **One render loop**, dt-clamped physics. Vibration amplitude follows the physics: `vibAmplitude(tC) = 0.035·√(T(K)/298.15)` capped 0.3 — particles vibrate in place below the melting point and become free bouncing particles above it.
- **HUD sync**: kicker/title per section (from `data-kicker`/`data-title`), metric chips + 3 live metrics via `stage.updateHud()`, and an aria-live Arabic summary via `stage.setSummaryProvider()` (updates every 1.6s).

## API (all in app.js)

```js
const stage = createStage({ canvas, shell, heroVisual, sticky, hero, rail, hud: {…} });
stage.registerStructure(id, builder);   // builder(stage) => structure data
stage.show(id); stage.rebuild(); stage.currentId();
stage.palettes[type] = [base, glow];    // per atom type
stage.setTemperature(tC); stage.setMeltingPoint(mp | (st)=>mp); stage.isMolten();
stage.setField(0..10);                  // electron drift for sea structures
stage.strikeMetallic(); stage.strikeIonic(); stage.restoreStrikes();
stage.onSlipDone = (kind) => {…};       // update evidence text after strike ends
stage.updateHud({title?, kicker?, metrics?, type?, state?});
stage.observeSections((section, stage) => {…});  // scroll → mode switch
stage.tour(ids); stage.setPaused(bool); stage.reset(initialId, appHook);
stage.start(initialId);
stage.debug(extra?)                     // verification snapshot (use it!)
```

Helpers: `bindRange(sel, fn)`, `bindSegmented(sel, fn)`, `setActive(sel, predicate)`, `initQuiz({form, explanations, score, reset})`, and `stage.utils` (clamp, lerp, map, seededRandom, kelvin, vibAmplitude, kineticRatio, gridAtoms, nearestBonds).

## Stock structures (pre-registered)

`crystalline` (4³ grid), `amorphous` (64 random), `iodine` (I₂ pairs + weak links), `ice` (tetrahedral H-bonds), `c60` (buckyball, cage rotation + ghost cages, Euler V−E+F=2), `diamond` (tetrahedral C), `graphite` (hexagonal layers), `quartz` (SiO₂), `metallic` (cations + 48-electron sea, `sea:true`, `slip:"metal"`), `ionic` (NaCl-type lattice, ± charges drawn on atoms, `slip:"ionic"`; reads `stage.state.ionMaterial` 0=KCl/1=CaO colors — call `stage.rebuild()` after switching material).

## Physics patterns to reuse per lesson

- **Heat slider** → `stage.setTemperature(v)` + `stage.setMeltingPoint(mp)`: below mp particles vibrate in place; above mp they detach and bounce (molten), and HUD/evidence text must reflect the phase change. Melting point may be a function of lesson state (e.g. selected material).
- **Field slider** on a `sea` structure → `stage.setField(v)`: electrons drift; show relative current (reference: `v·0.18`).
- **Strike buttons** on `slip` structures: metal → top layers slide and stay bonded (malleable); ionic → layers slide, like-charges align, repulsion pulses appear, gap opens, crack line draws (brittle). Update `.evidence-strip` and `.model-note` in `stage.onSlipDone`.
- **Neutral charge invariant**: ionic structures must sum to 0; metallic must have cation count == electron count. `stage.debug()` verifies both — always check in the verification step.

## Writing custom structures

Compose atoms in the world box, pick a palette per atom `type`, derive bonds with `nearestBonds(atoms, perAtom, maxDist, kind)`. Flags: `cage:true` (rotating cage rendering), `sea:true` (electron sea), `slip:"metal"|"ionic"` (enables strike machinery with layer threshold `home.y > 0.05` and 0.33 spacing — mirror stock spacing for reliable strikes).

## Verification snapshot

After building a lesson, run in the browser console (or headless test): `stage.debug()` must show `chargeNeutral:true`, `electronCountConserved:true`, `atomsWithinExpectedAmplitude:true`, `atomsInsideWorldBounds:true`, `consoleErrors:0`, and `canvasCounts:{sceneInit:1, loops:1}` (single loop). Test at 390/768/1440px, drag the stage, move every slider, strike, melt, and reset.
