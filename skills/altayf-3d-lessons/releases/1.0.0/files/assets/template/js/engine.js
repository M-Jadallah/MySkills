/* engine.js — pseudo-3D stage engine for Al-Tayf lesson pages.
 * One canvas, one animation loop, one persistent atom pool. No dependencies.
 * The lesson's app.js registers structures, wires control panels, and calls stage methods.
 * Proven architecture from the "الحالة الصلبة" reference lesson — keep the same IDs in index.html.
 */
"use strict";

const $ = (s, scope = document) => scope.querySelector(s);
const $$ = (s, scope = document) => [...scope.querySelectorAll(s)];
const clamp = (v, min, max) => Math.min(max, Math.max(min, v));
const lerp = (a, b, t) => a + (b - a) * t;
const map = (v, a, b, c, d) => c + ((v - a) / (b - a)) * (d - c);
const R_GAS = 8.314462618;
const WORLD = Object.freeze({ x: 0.86, yTop: 0.78, yBottom: -0.78, z: 0.68 });

function seededRandom(i) {
  const x = Math.sin(i * 999.17 + 4.31) * 43758.5453;
  return x - Math.floor(x);
}

/* ---------- scientific model ---------- */
function kelvin(tC) { return tC + 273.15; }
const A0 = 0.035, T_REF = 298.15;
function vibAmplitude(tC) { return Math.min(0.3, A0 * Math.sqrt(kelvin(tC) / T_REF)); }
function kineticRatio(tC) { return kelvin(tC) / T_REF; }
function escapeFraction(tC, em = 2400) { return Math.exp(-em / (R_GAS * kelvin(tC))); }

/* ---------- structure data helpers ---------- */
function gridAtoms(n, spacing, type = "cryst") {
  const atoms = [];
  const start = -spacing * (n - 1) / 2;
  for (let i = 0; i < n; i++) for (let j = 0; j < n; j++) for (let k = 0; k < n; k++) {
    atoms.push({ x: start + i * spacing, y: start + j * spacing, z: start + k * spacing, type, charge: 0, size: 1 });
  }
  return atoms;
}
function nearestBonds(atoms, perAtom, maxDist, kind) {
  const bonds = [], seen = new Set();
  atoms.forEach((a, i) => {
    atoms.map((b, j) => ({ j, d: Math.hypot(a.x - b.x, a.y - b.y, a.z - b.z) }))
      .filter(o => o.j !== i && o.d <= maxDist).sort((p, q) => p.d - q.d).slice(0, perAtom)
      .forEach(o => {
        const key = i < o.j ? `${i}-${o.j}` : `${o.j}-${i}`;
        if (!seen.has(key)) { seen.add(key); bonds.push({ a: i, b: o.j, kind }); }
      });
  });
  return bonds;
}

/* ---------- stock structure library (proven builders; register more in app.js) ---------- */
function buildCrystalline() {
  const atoms = gridAtoms(4, 0.34);
  return { atoms, bonds: nearestBonds(atoms, 3, 0.36, "strong"), coordination: 6 };
}
function buildAmorphous() {
  const atoms = [];
  for (let i = 0; i < 64; i++) {
    const th = seededRandom(i * 3 + 1) * Math.PI * 2;
    const ph = Math.acos(2 * seededRandom(i * 3 + 2) - 1);
    const r = 0.62 * Math.cbrt(seededRandom(i * 3 + 3));
    atoms.push({ x: r * Math.sin(ph) * Math.cos(th) * 1.25, y: r * Math.cos(ph) * 1.1, z: r * Math.sin(ph) * Math.sin(th), type: "amorph", charge: 0, size: 1 });
  }
  return { atoms, bonds: nearestBonds(atoms, 2, 0.34, "weak"), coordination: 0 };
}
function buildIodine() {
  const atoms = [], bonds = [], pairCenters = [];
  const n = 3, s = 0.42, start = -s * (n - 1) / 2;
  let idx = 0;
  for (let i = 0; i < n; i++) for (let j = 0; j < n; j++) for (let k = 0; k < n; k++) {
    const cx = start + i * s, cy = start + j * s, cz = start + k * s;
    const tilt = (i + j + k) % 2 === 0 ? 1 : -1;
    atoms.push({ x: cx - 0.09 * tilt, y: cy, z: cz - 0.05, type: "iodine", charge: 0, size: 1 });
    atoms.push({ x: cx + 0.09 * tilt, y: cy, z: cz + 0.05, type: "iodine", charge: 0, size: 1 });
    bonds.push({ a: idx, b: idx + 1, kind: "covalent" });
    pairCenters.push({ i: idx, x: cx, y: cy, z: cz });
    idx += 2;
  }
  const seen = new Set();
  pairCenters.forEach((p, pi) => {
    pairCenters.map((q, qi) => ({ qi, d: Math.hypot(p.x - q.x, p.y - q.y, p.z - q.z) }))
      .filter(o => o.qi !== pi).sort((a2, b2) => a2.d - b2.d).slice(0, 2)
      .forEach(o => {
        const key = pi < o.qi ? `${pi}-${o.qi}` : `${o.qi}-${pi}`;
        if (!seen.has(key)) { seen.add(key); bonds.push({ a: pairCenters[pi].i, b: pairCenters[o.qi].i, kind: "weak" }); }
      });
  });
  return { atoms, bonds, coordination: 1 };
}
function buildIce() {
  const a = 0.34;
  const base = [[-a, -a, -a], [a, -a, -a], [-a, a, -a], [a, a, -a], [-a, -a, a], [a, -a, a], [-a, a, a], [a, a, a],
    [0, -a, 0], [0, a, 0], [-a, 0, 0], [a, 0, 0], [0, 0, -a], [0, 0, a],
    [a / 2, a / 2, a / 2], [-a / 2, -a / 2, a / 2], [-a / 2, a / 2, -a / 2], [a / 2, -a / 2, -a / 2]];
  const atoms = base.map(p => ({ x: p[0], y: p[1], z: p[2], type: "oxygen", charge: 0, size: 1 }));
  return { atoms, bonds: nearestBonds(atoms, 4, 0.62, "hbond"), coordination: 4 };
}
function buildC60() {
  const atoms = [];
  const golden = Math.PI * (3 - Math.sqrt(5));
  for (let i = 0; i < 60; i++) {
    const y = 1 - (i / 59) * 2;
    const rad = Math.sqrt(Math.max(0, 1 - y * y));
    const th = golden * i;
    atoms.push({ x: 0.52 * Math.cos(th) * rad, y: 0.52 * y, z: 0.52 * Math.sin(th) * rad, type: "carbon", charge: 0, size: 0.72 });
  }
  return { atoms, bonds: nearestBonds(atoms, 3, 0.34, "covalent"), coordination: 3, cage: true, euler: { V: 60, E: 90, F: 32, identity: 2 } };
}
function buildDiamond() {
  const a = 0.44;
  const pts = [[-a, -a, -a], [a, -a, -a], [-a, a, -a], [a, a, -a], [-a, -a, a], [a, -a, a], [-a, a, a], [a, a, a],
    [0, -a, 0], [0, a, 0], [-a, 0, 0], [a, 0, 0], [0, 0, -a], [0, 0, a],
    [a / 2, a / 2, a / 2], [-a / 2, -a / 2, a / 2], [-a / 2, a / 2, -a / 2], [a / 2, -a / 2, -a / 2]];
  const atoms = pts.map(p => ({ x: p[0], y: p[1], z: p[2], type: "carbon", charge: 0, size: 0.92 }));
  const interior = [14, 15, 16, 17], bonds = [];
  interior.forEach(i => {
    atoms.map((b, j) => ({ j, d: Math.hypot(atoms[i].x - b.x, atoms[i].y - b.y, atoms[i].z - b.z) }))
      .filter(o => o.j !== i).sort((p, q) => p.d - q.d).slice(0, 4)
      .forEach(o => bonds.push({ a: i, b: o.j, kind: "covalent" }));
  });
  const seen = new Set();
  return { atoms, bonds: bonds.filter(b => { const k = b.a < b.b ? `${b.a}-${b.b}` : `${b.b}-${b.a}`; if (seen.has(k)) return false; seen.add(k); return true; }), coordination: 4 };
}
function buildGraphite() {
  const atoms = [], bonds = [], layerStart = [];
  const b = 0.21, layers = [-0.3, 0, 0.3];
  layers.forEach((ly, li) => {
    layerStart.push(atoms.length);
    for (let i = 0; i < 3; i++) for (let j = 0; j < 3; j++) {
      const baseX = (i - 1) * 1.5 * b * 2;
      const baseZ = (j - 1) * Math.sqrt(3) * b + (i % 2 ? Math.sqrt(3) / 2 * b : 0);
      atoms.push({ x: baseX, y: ly, z: baseZ, type: "carbon", charge: 0, size: 0.8, layer: li });
      atoms.push({ x: baseX + b, y: ly, z: baseZ, type: "carbon", charge: 0, size: 0.8, layer: li });
    }
  });
  layerStart.forEach((startIdx, li) => {
    const endIdx = li < layerStart.length - 1 ? layerStart[li + 1] : atoms.length;
    atoms.slice(startIdx, endIdx).forEach((a2, ii) => {
      atoms.slice(startIdx, endIdx).map((b2, jj) => ({ jj, d: Math.hypot(a2.x - b2.x, a2.z - b2.z) }))
        .filter(o => o.jj !== ii && o.d <= b * 1.15).sort((p, q) => p.d - q.d).slice(0, 3)
        .forEach(o => {
          const g1 = startIdx + ii, g2 = startIdx + o.jj;
          const key = g1 < g2 ? `${g1}-${g2}` : `${g2}-${g1}`;
          if (!bonds.some(x => `${x.a}-${x.b}` === key || `${x.b}-${x.a}` === key)) bonds.push({ a: g1, b: g2, kind: "covalent" });
        });
    });
  });
  for (let g = 0; g < 6; g++) bonds.push({ a: g * 2, b: Math.min(atoms.length - 1, g * 2 + 18), kind: "weak" });
  return { atoms, bonds, coordination: 3 };
}
function buildQuartz() {
  const t = 0.4;
  const outer = [[t, t, t], [-t, -t, t], [-t, t, -t], [t, -t, -t]];
  const atoms = [[0, 0, 0], ...outer].map(p => ({ x: p[0], y: p[1], z: p[2], type: "silicon", charge: 0, size: 1 }));
  const siLinks = [[0, 1], [0, 2], [0, 3], [0, 4], [1, 2], [2, 3], [3, 4], [4, 1]];
  const bonds = [];
  siLinks.forEach(([s1, s2]) => {
    const p1 = atoms[s1], p2 = atoms[s2];
    atoms.push({ x: (p1.x + p2.x) / 2, y: (p1.y + p2.y) / 2, z: (p1.z + p2.z) / 2, type: "oxygenRed", charge: 0, size: 0.62 });
    const oi = atoms.length - 1;
    bonds.push({ a: s1, b: oi, kind: "covalent" }, { a: s2, b: oi, kind: "covalent" });
  });
  outer.forEach((p, i2) => {
    const dir = Math.hypot(p[0], p[1], p[2]);
    atoms.push({ x: p[0] + (p[0] / dir) * 0.3, y: p[1] + (p[1] / dir) * 0.3, z: p[2] + (p[2] / dir) * 0.3, type: "oxygenRed", charge: 0, size: 0.62 });
    bonds.push({ a: i2 + 1, b: atoms.length - 1, kind: "covalent" });
  });
  return { atoms, bonds, coordination: 4 };
}
function buildMetallic() {
  const atoms = [];
  const nx = 4, ny = 3, nz = 4, s = 0.32;
  for (let i = 0; i < nx; i++) for (let j = 0; j < ny; j++) for (let k = 0; k < nz; k++) {
    atoms.push({ x: (i - (nx - 1) / 2) * s + (j % 2 ? s / 3 : 0), y: (j - (ny - 1) / 2) * s, z: (k - (nz - 1) / 2) * s + (j % 2 ? s / 3 : 0), type: "gold", charge: 1, size: 1.06 });
  }
  return { atoms, bonds: [], coordination: 12, sea: true, slip: "metal" };
}
function buildIonic(stage) {
  const material = stage?.state?.ionMaterial || 0;
  const atoms = [];
  const n = 4, s = 0.33;
  for (let i = 0; i < n; i++) for (let j = 0; j < n; j++) for (let k = 0; k < n; k++) {
    const positive = (i + j + k) % 2 === 0;
    atoms.push({ x: (i - (n - 1) / 2) * s, y: (j - (n - 1) / 2) * s, z: (k - (n - 1) / 2) * s,
      type: material === 0 ? (positive ? "kplus" : "clminus") : (positive ? "caplus" : "ominus"),
      charge: positive ? 1 : -1, size: positive ? 0.86 : 1.06 });
  }
  const bonds = [];
  atoms.forEach((a2, i2) => atoms.forEach((b2, j2) => {
    if (j2 <= i2) return;
    const d = Math.hypot(a2.x - b2.x, a2.y - b2.y, a2.z - b2.z);
    if (Math.abs(d - 0.33) < 0.02 && a2.charge !== b2.charge) bonds.push({ a: i2, b: j2, kind: "ionic" });
  }));
  return { atoms, bonds, coordination: 6, slip: "ionic" };
}

const DEFAULT_PALETTES = {
  cryst: ["#0b70a8", "rgba(70,220,235,.96)"],
  amorph: ["#5c4d9e", "rgba(178,154,255,.95)"],
  iodine: ["#5b2d8e", "rgba(187,128,255,.96)"],
  oxygen: ["#0a7fa8", "rgba(112,214,238,.96)"],
  carbon: ["#26343f", "rgba(150,180,200,.9)"],
  silicon: ["#0a2a49", "rgba(84,140,190,.95)"],
  oxygenRed: ["#a83a3a", "rgba(255,140,120,.95)"],
  gold: ["#a5760a", "rgba(255,206,92,.96)"],
  kplus: ["#2456a8", "rgba(110,160,255,.96)"],
  clminus: ["#0f7a4d", "rgba(90,230,170,.96)"],
  caplus: ["#b05e0a", "rgba(255,180,90,.96)"],
  ominus: ["#a83a3a", "rgba(255,120,110,.96)"]
};

/* ================= createStage ================= */
function createStage(config) {
  const canvas = $(config.canvas);
  const ctx = canvas.getContext("2d", { alpha: true });
  const shell = $(config.shell);
  const heroVisual = $(config.heroVisual);
  const stickyStage = $(config.sticky);
  const hero = $(config.hero);
  const rail = config.rail ? $(config.rail) : null;
  const hud = Object.fromEntries(Object.entries(config.hud || {}).map(([k, v]) => [k, $(v)]));

  window.__SCIENCE_DEBUG__ = { sceneInitCount: { stage: 1 }, rendererCreateCount: { stage: 1 }, activeAnimationLoops: 1, frameCount: 0, sectionModeChanges: 0, scientificUpdates: 0, consoleErrors: 0 };
  window.addEventListener("error", () => { window.__SCIENCE_DEBUG__.consoleErrors++; });

  /* ---------- lesson-facing state ---------- */
  const stage = {
    state: {},                    // app-owned bag; builders receive `stage`
    palettes: { ...DEFAULT_PALETTES },
    utils: { clamp, lerp, map, seededRandom, kelvin, vibAmplitude, kineticRatio, escapeFraction, gridAtoms, nearestBonds, $, $$ },
    paused: false,
  };

  /* ---------- internals ---------- */
  const builders = {
    crystalline: buildCrystalline, amorphous: buildAmorphous, iodine: buildIodine,
    ice: buildIce, c60: buildC60, diamond: buildDiamond, graphite: buildGraphite,
    quartz: buildQuartz, metallic: buildMetallic, ionic: buildIonic,
  };
  const MAX_ATOMS = config.maxAtoms || 80;
  const atoms = [];
  for (let i = 0; i < MAX_ATOMS; i++) {
    atoms.push({ active: false, x: 0, y: 0, z: 0, home: { x: 0, y: 0, z: 0 }, from: { x: 0, y: 0, z: 0 }, slip: { x: 0, y: 0, z: 0 }, type: "cryst", charge: 0, size: 1, phase: seededRandom(i * 7 + 3) * Math.PI * 2, vx: 0, vy: 0, vz: 0, free: false, morph: 1, layer: undefined });
  }
  const ELECTRON_COUNT = config.electronCount ?? 48;
  const electrons = [];
  for (let i = 0; i < ELECTRON_COUNT; i++) {
    electrons.push({ x: map(seededRandom(i * 11 + 1), 0, 1, -0.8, 0.8), y: map(seededRandom(i * 11 + 2), 0, 1, -0.7, 0.7), z: map(seededRandom(i * 11 + 3), 0, 1, -0.62, 0.62), vx: map(seededRandom(i * 11 + 4), 0, 1, -0.3, 0.3), vy: map(seededRandom(i * 11 + 5), 0, 1, -0.3, 0.3), vz: map(seededRandom(i * 11 + 6), 0, 1, -0.3, 0.3) });
  }

  let bonds = [];
  let currentId = "crystalline";
  let currentMeta = builders.crystalline(stage);
  let cageRot = 0;
  let moltenActive = false;
  let temperature = 25;
  let meltingPoint = null;         // number | (stage)=>number | null (never melts)
  let field = 0;
  let summaryProvider = null;
  let summaryClock = 0;
  let width = 900, height = 540, dpr = 1, lastTime = performance.now();
  let rotationY = -0.18, rotationX = 0.08, targetRotationY = rotationY, targetRotationX = rotationX;
  let dragging = false, pointerStart = null;
  let stageInHero = true;

  const metalSlip = { progress: 0, done: false, running: false };
  const ionicSlip = { progress: 0, running: false, fractured: false, repelPairs: [], gap: 0 };
  stage.metalSlip = metalSlip;
  stage.ionicSlip = ionicSlip;

  function setStructure(id) {
    const build = builders[id];
    if (!build) throw new Error(`Unknown structure: ${id}`);
    const s = build(stage);
    atoms.forEach((atom, i) => {
      if (i < s.atoms.length) {
        const t = s.atoms[i];
        atom.from = { x: atom.x, y: atom.y, z: atom.z };
        atom.home = { x: t.x, y: t.y, z: t.z };
        atom.slip = { x: 0, y: 0, z: 0 };
        atom.type = t.type; atom.charge = t.charge || 0; atom.size = t.size || 1; atom.layer = t.layer;
        atom.active = true; atom.free = false; atom.morph = 0; atom.vx = 0; atom.vy = 0; atom.vz = 0;
      } else atom.active = false;
    });
    bonds = s.bonds.map(b => ({ ...b }));
    currentId = id;
    currentMeta = s;
    moltenActive = false;
    metalSlip.progress = 0; metalSlip.done = false; metalSlip.running = false;
    ionicSlip.progress = 0; ionicSlip.running = false; ionicSlip.fractured = false; ionicSlip.repelPairs = []; ionicSlip.gap = 0;
  }

  const moltenNow = () => meltingPoint !== null && temperature >= (typeof meltingPoint === "function" ? meltingPoint(stage) : meltingPoint);

  function updateAtoms(dt, dtAnim, now) {
    const amp = vibAmplitude(temperature);
    const speed = 2.2 + map(clamp(temperature, -50, 3000), -50, 3000, 0, 7);
    const molten = moltenNow();
    if (molten && !moltenActive) atoms.forEach(a2 => { if (a2.active) { a2.free = true; a2.vx = map(seededRandom(a2.phase * 91 + 1), 0, 1, -0.25, 0.25); a2.vy = map(seededRandom(a2.phase * 91 + 2), 0, 1, -0.22, 0.22); a2.vz = map(seededRandom(a2.phase * 91 + 3), 0, 1, -0.25, 0.25); } });
    if (!molten && moltenActive) atoms.forEach(a2 => { if (a2.active) { a2.free = false; a2.from = { x: a2.x, y: a2.y, z: a2.z }; a2.morph = 0; } });
    moltenActive = molten;

    const bx = WORLD.x - 0.1, by = WORLD.yTop - 0.12, bz = WORLD.z - 0.09;
    atoms.forEach(a2 => {
      if (!a2.active) return;
      if (a2.morph < 1) a2.morph = Math.min(1, a2.morph + dtAnim * 2.4);
      const e = a2.morph * a2.morph * (3 - 2 * a2.morph);
      const hx = lerp(a2.from.x, a2.home.x, e) + a2.slip.x;
      const hy = lerp(a2.from.y, a2.home.y, e) + a2.slip.y;
      const hz = lerp(a2.from.z, a2.home.z, e) + a2.slip.z;
      if (a2.free) {
        const th = 0.8 + map(temperature, 25, 3000, 0, 1.4);
        a2.vx += Math.sin(now * 0.0013 + a2.phase) * 0.12 * dt * th;
        a2.vy += Math.cos(now * 0.0011 + a2.phase * 1.3) * 0.11 * dt * th;
        a2.vz += Math.sin(now * 0.0009 + a2.phase * 0.7) * 0.12 * dt * th;
        const sp = Math.hypot(a2.vx, a2.vy, a2.vz) || 1;
        const limit = 0.34 + map(temperature, 25, 3000, 0, 0.3);
        if (sp > limit) { a2.vx *= limit / sp; a2.vy *= limit / sp; a2.vz *= limit / sp; }
        a2.x += a2.vx * dt; a2.y += a2.vy * dt; a2.z += a2.vz * dt;
        if (Math.abs(a2.x) > bx) { a2.x = clamp(a2.x, -bx, bx); a2.vx *= -0.9; }
        if (a2.y > by || a2.y < -by) { a2.y = clamp(a2.y, -by, by); a2.vy *= -0.9; }
        if (Math.abs(a2.z) > bz) { a2.z = clamp(a2.z, -bz, bz); a2.vz *= -0.9; }
      } else {
        const w = speed * (0.8 + seededRandom(Math.round(a2.phase * 100)) * 0.4);
        a2.x = hx + amp * Math.sin(now * 0.001 * w + a2.phase);
        a2.y = hy + amp * Math.sin(now * 0.00113 * w + a2.phase * 1.7);
        a2.z = hz + amp * Math.cos(now * 0.00097 * w + a2.phase * 0.6);
      }
    });
  }

  function updateElectrons(dt, now) {
    const drift = -0.16 * field;
    electrons.forEach((e2, i) => {
      e2.vx += (Math.sin(now * 0.0016 + i) * 0.35 + drift - e2.vx * 0.6) * dt;
      e2.vy += (Math.cos(now * 0.0014 + i * 1.7) * 0.3 - e2.vy * 0.6) * dt;
      e2.vz += (Math.sin(now * 0.0012 + i * 0.6) * 0.3 - e2.vz * 0.6) * dt;
      e2.x += e2.vx * dt; e2.y += e2.vy * dt; e2.z += e2.vz * dt;
      if (e2.x < -0.84) e2.x = 0.84; if (e2.x > 0.84) e2.x = -0.84;
      if (e2.y < -0.74) e2.y = 0.74; if (e2.y > 0.74) e2.y = -0.74;
      if (e2.z < -0.64) e2.z = 0.64; if (e2.z > 0.64) e2.z = -0.64;
    });
  }

  function updateMetalSlip(dt) {
    if (metalSlip.running && metalSlip.progress < 1) {
      metalSlip.progress = Math.min(1, metalSlip.progress + dt * 1.15);
      if (metalSlip.progress >= 1) { metalSlip.done = true; metalSlip.running = false; stage.onSlipDone?.("metal"); }
    }
    const e = metalSlip.progress * metalSlip.progress * (3 - 2 * metalSlip.progress);
    atoms.forEach(a2 => { if (a2.active && currentMeta.slip === "metal") a2.slip.x = a2.home.y > 0.05 ? 0.24 * e : 0; });
  }

  function updateIonicSlip(dt) {
    if (ionicSlip.running && ionicSlip.progress < 1) {
      ionicSlip.progress = Math.min(1, ionicSlip.progress + dt * 1.3);
      if (ionicSlip.progress >= 1) {
        ionicSlip.running = false;
        ionicSlip.repelPairs = [];
        const s = 0.33;
        atoms.forEach((top, ti) => {
          if (!top.active || top.home.y <= 0.05) return;
          let best = -1, bestD = 1e9;
          atoms.forEach((bot, bi) => {
            if (!bot.active || bot.home.y > 0.05) return;
            const d = Math.hypot(bot.home.x - (top.home.x + s), bot.home.z - top.home.z) + Math.abs(bot.home.y - (top.home.y - s));
            if (d < bestD) { bestD = d; best = bi; }
          });
          if (best >= 0 && atoms[best].charge === top.charge) ionicSlip.repelPairs.push([ti, best]);
        });
      }
    }
    if (!ionicSlip.running && ionicSlip.progress >= 1 && ionicSlip.repelPairs.length > 0 && ionicSlip.gap < 0.16) {
      ionicSlip.gap = Math.min(0.16, ionicSlip.gap + dt * 0.09);
      if (ionicSlip.gap >= 0.16 && !ionicSlip.fractured) { ionicSlip.fractured = true; stage.onSlipDone?.("ionic"); }
    }
    const e = ionicSlip.progress * ionicSlip.progress * (3 - 2 * ionicSlip.progress);
    atoms.forEach(a2 => {
      if (!a2.active || currentMeta.slip !== "ionic") return;
      if (a2.home.y > 0.05) { a2.slip.x = 0.33 * e; a2.slip.y = ionicSlip.gap; }
      else { a2.slip.x = 0; a2.slip.y = -ionicSlip.gap * 0.35; }
    });
  }

  /* ---------- projection & drawing ---------- */
  function resizeCanvas() {
    const rect = shell.getBoundingClientRect();
    width = Math.max(300, Math.round(rect.width));
    height = Math.max(260, Math.round(rect.height));
    dpr = Math.min(2, window.devicePixelRatio || 1);
    const nextW = Math.round(width * dpr), nextH = Math.round(height * dpr);
    if (canvas.width !== nextW || canvas.height !== nextH) {
      canvas.width = nextW; canvas.height = nextH;
      canvas.style.width = `${width}px`; canvas.style.height = `${height}px`;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    }
  }
  function stageGeometry() {
    const w = Math.min(width * 0.78, 560), h = Math.min(height * 0.62, 360);
    return { cx: width / 2, cy: height * 0.52, halfW: w / 2, halfH: h / 2 };
  }
  function project(p, geometry) {
    const g = geometry || stageGeometry();
    const cosy = Math.cos(rotationY), siny = Math.sin(rotationY);
    const cosx = Math.cos(rotationX), sinx = Math.sin(rotationX);
    const x1 = p.x * cosy - p.z * siny, z1 = p.x * siny + p.z * cosy;
    const y1 = p.y * cosx - z1 * sinx, z2 = p.y * sinx + z1 * cosx;
    const perspective = clamp(1 / (1 + z2 * 0.18), 0.82, 1.18);
    return { x: g.cx + (x1 / WORLD.x) * g.halfW * perspective, y: g.cy - (y1 / 0.82) * g.halfH * perspective, z: z2, scale: perspective };
  }
  function drawAtom(a2, q) {
    const colors = stage.palettes[a2.type] || stage.palettes.cryst;
    const r = clamp(9.2 * a2.size * q.scale, 4.5, 16);
    ctx.save();
    ctx.fillStyle = colors[0];
    ctx.beginPath(); ctx.arc(q.x, q.y, r, 0, Math.PI * 2); ctx.fill();
    ctx.strokeStyle = colors[1]; ctx.lineWidth = Math.max(1, r * 0.12); ctx.stroke();
    ctx.globalAlpha = 0.72; ctx.fillStyle = "#fff";
    ctx.beginPath(); ctx.arc(q.x - r * 0.32, q.y - r * 0.34, Math.max(1.2, r * 0.2), 0, Math.PI * 2); ctx.fill();
    ctx.globalAlpha = 1;
    if (a2.charge !== 0 && r > 6) {
      ctx.fillStyle = "rgba(255,255,255,.92)";
      ctx.font = `900 ${Math.round(r * 1.05)}px Tahoma`;
      ctx.textAlign = "center"; ctx.textBaseline = "middle";
      ctx.fillText(a2.charge > 0 ? "+" : "−", q.x, q.y + 0.5);
    }
    ctx.restore();
  }
  function bondStyle(kind) {
    switch (kind) {
      case "covalent": return { color: "rgba(140,220,240,.62)", width: 2.4, dash: [] };
      case "hbond": return { color: "rgba(90,190,230,.5)", width: 1.6, dash: [5, 5] };
      case "weak": return { color: "rgba(170,150,235,.4)", width: 1.3, dash: [3, 6] };
      case "ionic": return { color: "rgba(150,210,255,.34)", width: 1.4, dash: [6, 6] };
      case "repel": return { color: "rgba(255,84,84,.9)", width: 3, dash: [2, 4] };
      default: return { color: "rgba(96,200,228,.5)", width: 1.9, dash: [] };
    }
  }
  function drawBonds(projected) {
    ctx.save();
    bonds.forEach(b2 => {
      const pa = projected[b2.a], pb = projected[b2.b];
      if (!pa || !pb) return;
      const style = bondStyle(b2.kind);
      const depth = clamp((pa.q.z + pb.q.z) / 2 * 0.5 + 0.5, 0, 1);
      ctx.strokeStyle = style.color;
      ctx.lineWidth = style.width * (0.7 + depth * 0.6);
      ctx.setLineDash(style.dash);
      ctx.globalAlpha = 0.45 + depth * 0.55;
      ctx.beginPath(); ctx.moveTo(pa.q.x, pa.q.y); ctx.lineTo(pb.q.x, pb.q.y); ctx.stroke();
    });
    ctx.restore();
  }
  function drawRepelPairs(projected) {
    if (!ionicSlip.repelPairs.length) return;
    ctx.save();
    const pulse = 0.55 + Math.sin(performance.now() * 0.006) * 0.3;
    ionicSlip.repelPairs.forEach(([ai, bi]) => {
      const pa = projected[ai], pb = projected[bi];
      if (!pa || !pb) return;
      ctx.strokeStyle = "rgba(255,84,84,.9)"; ctx.lineWidth = 3; ctx.setLineDash([2, 4]); ctx.globalAlpha = pulse;
      ctx.beginPath(); ctx.moveTo(pa.q.x, pa.q.y); ctx.lineTo(pb.q.x, pb.q.y); ctx.stroke();
    });
    ctx.restore();
  }
  function drawElectrons(g) {
    ctx.save();
    electrons.forEach(e2 => {
      const q = project(e2, g);
      ctx.fillStyle = "rgba(126,232,255,.85)";
      ctx.beginPath(); ctx.arc(q.x, q.y, clamp(2.6 * q.scale, 1.4, 3.4), 0, Math.PI * 2); ctx.fill();
    });
    ctx.restore();
  }
  function drawCrackLine(g) {
    if (!ionicSlip.fractured) return;
    ctx.save();
    ctx.strokeStyle = "rgba(255,120,110,.85)"; ctx.lineWidth = 2.4; ctx.setLineDash([7, 5]);
    const y0 = g.cy - (0.1 / 0.82) * g.halfH;
    ctx.beginPath();
    let x = g.cx - g.halfW * 0.9, y = y0;
    ctx.moveTo(x, y);
    for (let i = 1; i <= 12; i++) { x = g.cx - g.halfW * 0.9 + (g.halfW * 1.8 * i) / 12; y = y0 + (i % 2 ? -9 : 9); ctx.lineTo(x, y); }
    ctx.stroke();
    ctx.restore();
  }
  function drawGhostCages(g) {
    ctx.save();
    ctx.globalAlpha = 0.22;
    const meta = builders.c60(stage);
    [[-1.15, -0.5, -0.4], [1.15, 0.5, 0.4]].forEach(off => {
      meta.atoms.map(a2 => project({ x: a2.x * 0.5 + off[0], y: a2.y * 0.5 + off[1], z: a2.z * 0.5 + off[2] }, g)).forEach(q => {
        ctx.fillStyle = "rgba(150,120,220,.8)";
        ctx.beginPath(); ctx.arc(q.x, q.y, 3, 0, Math.PI * 2); ctx.fill();
      });
    });
    ctx.restore();
  }
  function drawScene() {
    ctx.clearRect(0, 0, width, height);
    ctx.fillStyle = "rgba(9,54,82,.16)"; ctx.fillRect(0, 0, width, height);
    const g = stageGeometry();
    ctx.save();
    ctx.fillStyle = "rgba(6,24,44,.45)";
    ctx.beginPath(); ctx.ellipse(g.cx, g.cy + g.halfH * 0.92, g.halfW * 0.8, 16, 0, 0, Math.PI * 2); ctx.fill();
    ctx.restore();

    let drawList = atoms.filter(a2 => a2.active);
    if (currentMeta.cage) {
      const cs = Math.cos(cageRot), sn = Math.sin(cageRot);
      drawList = drawList.map(a2 => {
        const rx = a2.x * cs - a2.z * sn, rz = a2.x * sn + a2.z * cs;
        return { atom: a2, q: project({ x: rx, y: a2.y, z: rz }, g) };
      });
      ctx.save();
      bonds.forEach(b2 => {
        const pa = drawList[b2.a], pb = drawList[b2.b];
        if (!pa || !pb) return;
        ctx.strokeStyle = "rgba(190,160,255,.55)"; ctx.lineWidth = 1.7;
        ctx.beginPath(); ctx.moveTo(pa.q.x, pa.q.y); ctx.lineTo(pb.q.x, pb.q.y); ctx.stroke();
      });
      ctx.restore();
      drawList.sort((p, q2) => p.q.z - q2.q.z).forEach(item => drawAtom(item.atom, item.q));
      drawGhostCages(g);
      return;
    }
    const projected = drawList.map(a2 => ({ atom: a2, q: project(a2, g) }));
    if (currentMeta.sea) drawElectrons(g);
    drawBonds(projected);
    drawRepelPairs(projected);
    projected.sort((p, q2) => p.q.z - q2.q.z);
    projected.forEach(item => drawAtom(item.atom, item.q));
    drawCrackLine(g);
  }

  /* ---------- HUD & accessible summary ---------- */
  stage.updateHud = (parts) => {
    if (parts.title !== undefined && hud.title) hud.title.textContent = parts.title;
    if (parts.kicker !== undefined && hud.kicker) hud.kicker.textContent = parts.kicker;
    if (parts.metrics && hud.metrics) hud.metrics.innerHTML = parts.metrics.map(m => `<span><i></i>${m}</span>`).join("");
    if (hud.temp) hud.temp.textContent = `${temperature.toFixed(0)} °C`;
    if (parts.type !== undefined && hud.type) hud.type.textContent = parts.type;
    if (parts.state !== undefined && hud.state) hud.state.textContent = parts.state;
  };
  stage.setSummaryProvider = (fn) => { summaryProvider = fn; };
  function updateSummary(now) {
    if (!summaryProvider || !hud.summary || now - summaryClock < 1600) return;
    summaryClock = now;
    hud.summary.textContent = summaryProvider(stage);
  }

  /* ---------- stage follows the lesson (hero ↔ sticky) ---------- */
  function moveStage(forceHero = null) {
    const shouldHero = forceHero === null ? window.scrollY < hero.offsetHeight * 0.58 : forceHero;
    if (shouldHero && !stageInHero) {
      heroVisual.appendChild(shell);
      shell.classList.add("hero-stage-shell");
      stageInHero = true;
      requestAnimationFrame(resizeCanvas);
    } else if (!shouldHero && stageInHero) {
      stickyStage.appendChild(shell);
      shell.classList.remove("hero-stage-shell");
      stageInHero = false;
      requestAnimationFrame(resizeCanvas);
    }
  }
  function updateProgress() {
    const scrollable = document.documentElement.scrollHeight - innerHeight;
    const bar = $("#readingProgress");
    if (bar) bar.style.width = `${scrollable > 0 ? clamp(scrollY / scrollable * 100, 0, 100) : 0}%`;
    $("#topbar")?.classList.toggle("scrolled", scrollY > 18);
    moveStage();
  }

  /* ---------- section observation ---------- */
  stage.observeSections = (onSection) => {
    const sections = [hero, ...$$(".content-section")];
    const obs = new IntersectionObserver(entries => {
      const visible = entries.filter(e2 => e2.isIntersecting).sort((a2, b2) => b2.intersectionRatio - a2.intersectionRatio)[0];
      if (!visible) return;
      const section = visible.target;
      window.__SCIENCE_DEBUG__.sectionModeChanges++;
      targetRotationX = clamp(targetRotationX, -0.24, 0.24);
      if (hud.title) hud.title.textContent = section.dataset.title || "";
      if (hud.kicker) hud.kicker.textContent = section.dataset.kicker || "";
      if (rail) $$("a", rail).forEach(a2 => a2.classList.toggle("active", a2.getAttribute("href") === `#${section.id}`));
      onSection(section, stage);
    }, { rootMargin: "-25% 0px -48% 0px", threshold: [0, 0.15, 0.35, 0.6] });
    sections.forEach(s2 => obs.observe(s2));
    window.addEventListener("scroll", updateProgress, { passive: true });
    window.addEventListener("resize", () => { resizeCanvas(); updateProgress(); });
  };

  /* ---------- strikes (metal slip / ionic fracture) ---------- */
  stage.strikeMetallic = () => { if (currentMeta.slip !== "metal") return; metalSlip.progress = 0; metalSlip.done = false; metalSlip.running = true; };
  stage.strikeIonic = () => { if (currentMeta.slip !== "ionic" || moltenNow()) return; ionicSlip.progress = 0; ionicSlip.running = true; ionicSlip.fractured = false; ionicSlip.repelPairs = []; ionicSlip.gap = 0; };
  stage.restoreStrikes = () => {
    metalSlip.progress = 0; metalSlip.done = false; metalSlip.running = false;
    ionicSlip.progress = 0; ionicSlip.running = false; ionicSlip.fractured = false; ionicSlip.repelPairs = []; ionicSlip.gap = 0;
    atoms.forEach(a2 => { a2.slip = { x: 0, y: 0, z: 0 }; });
  };

  /* ---------- public structure/temperature/field API ---------- */
  stage.registerStructure = (id, builder) => { builders[id] = builder; };
  stage.show = (id) => { if (id !== currentId) setStructure(id); };
  stage.rebuild = () => setStructure(currentId);   // re-run builder after state change (e.g. material switch)
  stage.currentId = () => currentId;
  stage.currentMeta = () => currentMeta;
  stage.setTemperature = (tC) => { temperature = clamp(Number(tC) || 25, -50, 3000); };
  stage.temperature = () => temperature;
  stage.isMolten = () => moltenNow();
  stage.setMeltingPoint = (mp) => { meltingPoint = mp; };
  stage.setField = (f) => { field = clamp(Number(f) || 0, 0, 10); };
  stage.electronCount = ELECTRON_COUNT;

  /* ---------- tour & pause & reset ---------- */
  stage.tour = async (ids, dwell = 900) => {
    for (const id of ids) {
      const section = document.getElementById(id);
      if (!section) continue;
      section.scrollIntoView({ behavior: "smooth", block: "center" });
      await new Promise(r2 => setTimeout(r2, dwell));
    }
  };
  stage.setPaused = (p) => {
    stage.paused = p;
    document.body.classList.toggle("motion-paused", p);
    const btn = $("#motionToggle");
    if (btn) btn.setAttribute("aria-label", p ? "تشغيل الحركة" : "إيقاف الحركة");
  };
  stage.reset = (initialId = "crystalline", appHook) => {
    setStructure(initialId);
    electrons.forEach((e2, i) => {
      e2.x = map(seededRandom(i * 11 + 1), 0, 1, -0.8, 0.8);
      e2.y = map(seededRandom(i * 11 + 2), 0, 1, -0.7, 0.7);
      e2.z = map(seededRandom(i * 11 + 3), 0, 1, -0.62, 0.62);
    });
    rotationY = targetRotationY = -0.18;
    rotationX = targetRotationX = 0.08;
    appHook?.(stage);
  };

  /* ---------- main loop ---------- */
  let running = false;
  function render(now) {
    const dtReal = (now - lastTime) / 1000 || 0.016;
    lastTime = now;
    const dt = Math.min(0.033, dtReal);
    const dtAnim = Math.min(0.3, dtReal);
    rotationY = lerp(rotationY, targetRotationY, 0.08);
    rotationX = lerp(rotationX, targetRotationX, 0.08);
    if (!stage.paused) {
      if (currentMeta.cage) cageRot += dt * 0.5;
      updateAtoms(dt, dtAnim, now);
      if (currentMeta.sea) updateElectrons(dt, now);
      if (currentMeta.slip === "metal") updateMetalSlip(dtAnim);
      if (currentMeta.slip === "ionic") updateIonicSlip(dtAnim);
    }
    drawScene();
    updateSummary(now);
    window.__SCIENCE_DEBUG__.frameCount++;
    if (running) requestAnimationFrame(render);
  }

  /* ---------- built-in chrome controls (wired if the elements exist) ---------- */
  function setupChrome() {
    $("#motionToggle")?.addEventListener("click", () => stage.setPaused(!stage.paused));
    const fsBtn = $("#fullscreenToggle");
    fsBtn?.addEventListener("click", async () => {
      if (document.fullscreenElement) await document.exitFullscreen();
      else if (shell.requestFullscreen) await shell.requestFullscreen();
      else shell.classList.toggle("pseudo-fullscreen");
      requestAnimationFrame(resizeCanvas);
    });
    document.addEventListener("fullscreenchange", () => {
      const active = document.fullscreenElement === shell || shell.classList.contains("pseudo-fullscreen");
      fsBtn?.setAttribute("aria-label", active ? "إنهاء عرض ملء الشاشة" : "عرض المحاكاة بملء الشاشة");
      const label = fsBtn?.querySelector("span");
      if (label) label.textContent = active ? "إنهاء ملء الشاشة" : "ملء الشاشة";
      requestAnimationFrame(resizeCanvas);
    });
    const navToggle = $("#mobileNavToggle"), mobileNav = $("#mobileNav");
    navToggle?.addEventListener("click", () => {
      const open = document.body.classList.toggle("mobile-nav-open");
      navToggle.setAttribute("aria-expanded", String(open));
      navToggle.setAttribute("aria-label", open ? "إغلاق قائمة أقسام الدرس" : "فتح قائمة أقسام الدرس");
    });
    if (mobileNav) $$("a", mobileNav).forEach(link => link.addEventListener("click", () => {
      document.body.classList.remove("mobile-nav-open");
      navToggle?.setAttribute("aria-expanded", "false");
    }));
    const collapseBtn = $("#stageCollapseToggle");
    collapseBtn?.addEventListener("click", () => {
      const collapsed = stickyStage.classList.toggle("collapsed");
      collapseBtn.setAttribute("aria-expanded", String(!collapsed));
      collapseBtn.textContent = collapsed ? "عرض المجسم" : "طي المجسم";
      if (!collapsed) requestAnimationFrame(resizeCanvas);
    });
    document.addEventListener("keydown", (event) => {
      if (event.key === "Escape" && document.body.classList.contains("mobile-nav-open")) {
        document.body.classList.remove("mobile-nav-open");
        navToggle?.setAttribute("aria-expanded", "false");
      }
    });
    canvas.addEventListener("pointerdown", e2 => {
      dragging = true;
      pointerStart = { x: e2.clientX, y: e2.clientY, ry: targetRotationY, rx: targetRotationX };
      canvas.setPointerCapture(e2.pointerId);
    });
    canvas.addEventListener("pointermove", e2 => {
      if (!dragging || !pointerStart) return;
      targetRotationY = pointerStart.ry + (e2.clientX - pointerStart.x) * 0.008;
      targetRotationX = clamp(pointerStart.rx + (e2.clientY - pointerStart.y) * 0.006, -0.24, 0.24);
    });
    const end = e2 => {
      dragging = false; pointerStart = null;
      if (canvas.hasPointerCapture?.(e2.pointerId)) canvas.releasePointerCapture(e2.pointerId);
    };
    canvas.addEventListener("pointerup", end);
    canvas.addEventListener("pointercancel", end);
  }

  /* ---------- verification snapshot ---------- */
  stage.debug = (extra = {}) => {
    const amp = vibAmplitude(temperature);
    let maxDisplacement = 0, allInside = true;
    const activeAtoms = atoms.filter(a2 => a2.active);
    const midMorph = activeAtoms.some(a2 => a2.morph < 1);
    activeAtoms.forEach(a2 => {
      if (!a2.free && a2.morph >= 1) {
        maxDisplacement = Math.max(maxDisplacement, Math.hypot(a2.x - (a2.home.x + a2.slip.x), a2.y - (a2.home.y + a2.slip.y), a2.z - (a2.home.z + a2.slip.z)));
      }
      if (Math.abs(a2.x) > WORLD.x + 0.001 || a2.y > WORLD.yTop + 0.001 || a2.y < WORLD.yBottom - 0.001 || Math.abs(a2.z) > WORLD.z + 0.001) allInside = false;
    });
    const chargeSum = activeAtoms.reduce((s2, a2) => s2 + a2.charge, 0);
    const cationCount = activeAtoms.filter(a2 => a2.charge > 0).length;
    const neutral = currentMeta.sea ? cationCount === electrons.length : chargeSum === 0;
    return {
      structureId: currentId, activeAtomCount: activeAtoms.length, bondCount: bonds.length,
      temperature, temperatureKelvin: kelvin(temperature), amplitude: amp,
      atomsWithinExpectedAmplitude: midMorph ? true : maxDisplacement <= amp * Math.sqrt(3) * 1.01 + 1e-6,
      molten: moltenActive, atomsInsideWorldBounds: allInside,
      chargeSum, cationCount, chargeNeutral: neutral,
      electronCount: electrons.length, electronCountConserved: electrons.length === ELECTRON_COUNT,
      metalSlipDone: metalSlip.done, ionicFractured: ionicSlip.fractured, ionicRepelPairCount: ionicSlip.repelPairs.length,
      canvasCounts: { sceneInit: window.__SCIENCE_DEBUG__.sceneInitCount.stage, loops: window.__SCIENCE_DEBUG__.activeAnimationLoops },
      frameCount: window.__SCIENCE_DEBUG__.frameCount, consoleErrors: window.__SCIENCE_DEBUG__.consoleErrors,
      ...extra,
    };
  };

  /* ---------- start ---------- */
  stage.start = (initialId = "crystalline") => {
    setStructure(initialId);
    resizeCanvas();
    setupChrome();
    updateProgress();
    running = true;
    requestAnimationFrame(render);
  };

  return stage;
}

/* ================= generic control helpers ================= */
function bindRange(selector, fn) {
  const el = typeof selector === "string" ? $(selector) : selector;
  if (!el) return;
  el.addEventListener("input", () => fn(Number(el.value), el));
}
function bindSegmented(selector, fn) {
  $$(selector).forEach(btn => btn.addEventListener("click", () => {
    fn(btn);
    window.__SCIENCE_DEBUG__ && window.__SCIENCE_DEBUG__.scientificUpdates++;
  }));
}
function setActive(selector, predicate) {
  $$(selector).forEach(btn => btn.classList.toggle("active", !!predicate(btn)));
}

/* ================= generic quiz engine =================
 * Form: <form id="quizForm" class="quiz"><fieldset data-answer="b"><legend>…</legend>
 *   <label><input type="radio" name="q1" value="a">…</label>…<p class="quiz-feedback"></p></fieldset>…
 * explanations: { q1: "…", q2: "…" } keyed by input name. */
function initQuiz({ form = "#quizForm", explanations = {}, score = "#quizScore", reset = "#resetQuiz" } = {}) {
  const formEl = $(form);
  if (!formEl) return;
  formEl.addEventListener("submit", e2 => {
    e2.preventDefault();
    let scoreCount = 0, total = 0;
    $$("fieldset", formEl).forEach(fs => {
      total++;
      const selected = $("input:checked", fs);
      const correct = selected && selected.value === fs.dataset.answer;
      fs.classList.toggle("correct", !!correct);
      fs.classList.toggle("incorrect", !correct);
      if (correct) scoreCount++;
      const fb = $(".quiz-feedback", fs);
      const why = explanations[selected?.name || $$("input", fs)[0]?.name] || "";
      if (fb) fb.textContent = `${correct ? "إجابة صحيحة." : "إجابة غير صحيحة."} ${why}`;
    });
    const out = $(score);
    if (out) out.textContent = `النتيجة: ${scoreCount} / ${total}`;
    window.__SCIENCE_DEBUG__ && window.__SCIENCE_DEBUG__.scientificUpdates++;
  });
  $(reset)?.addEventListener("click", () => {
    formEl.reset();
    $$("fieldset", formEl).forEach(fs => fs.classList.remove("correct", "incorrect"));
    const out = $(score);
    if (out) out.textContent = "لم يتم التصحيح بعد";
  });
}
