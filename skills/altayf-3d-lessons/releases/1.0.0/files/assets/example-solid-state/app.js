(() => {
  "use strict";

  const $ = (selector, scope = document) => scope.querySelector(selector);
  const $$ = (selector, scope = document) => [...scope.querySelectorAll(selector)];
  const clamp = (v, min, max) => Math.min(max, Math.max(min, v));
  const lerp = (a, b, t) => a + (b - a) * t;
  const map = (v, a, b, c, d) => c + ((v - a) / (b - a)) * (d - c);
  const R_GAS = 8.314462618;

  // World box for the pseudo-3D projection. +y is up (world-y-up convention).
  const WORLD = Object.freeze({ x: 0.86, yTop: 0.78, yBottom: -0.78, z: 0.68 });

  window.__SCIENCE_DEBUG__ = {
    sceneInitCount: { "solid-state": 1 },
    rendererCreateCount: { "solid-state": 1 },
    activeAnimationLoops: 1,
    frameCount: 0,
    sectionModeChanges: 0,
    lastMode: "solid",
    scientificUpdates: 0,
    consoleErrors: 0
  };
  window.addEventListener("error", () => { window.__SCIENCE_DEBUG__.consoleErrors++; });

  const canvas = $("#solidCanvas");
  const ctx = canvas.getContext("2d", { alpha: true });
  const stageShell = $("#stageShell");
  const heroVisual = $(".hero-visual");
  const stickyStage = $("#stickyStage");
  const hero = $("#hero");
  const stageTitle = $("#stageTitle");
  const stageKicker = $("#stageKicker");
  const hudMetrics = $("#hudMetrics");
  const hudTemp = $("#hudTemp");
  const hudType = $("#hudType");
  const hudState = $("#hudState");
  const simSummary = $("#simSummary");
  const fullscreenToggle = $("#fullscreenToggle");
  const mobileNavToggle = $("#mobileNavToggle");
  const mobileNav = $("#mobileNav");
  const stageCollapseToggle = $("#stageCollapseToggle");

  const defaults = Object.freeze({
    mode: "solid",
    temperature: 25,
    order: 0,
    molMaterial: 0,
    attraction: 3,
    netMaterial: 0,
    networkTemp: 25,
    field: 0,
    ionMaterial: 0,
    ionicTemp: 25,
    mp: 730,
    hardness: 5,
    sigmaS: 0,
    sigmaM: 1,
    brittle: 1,
    paused: false
  });

  const state = { ...defaults };
  let stageInHero = true;
  let activeSection = hero;
  let width = 900;
  let height = 540;
  let dpr = 1;
  let lastTime = performance.now();
  let rotationY = -0.18;
  let rotationX = 0.08;
  let targetRotationY = rotationY;
  let targetRotationX = rotationX;
  let dragging = false;
  let pointerStart = null;
  let summaryClock = 0;

  const DEMO_MELTING_POINT = 800; // Demo value declared in the UI for the generic solid.
  const A0 = 0.035;               // Vibration amplitude at 25 °C.
  const T_REF = 298.15;

  function seededRandom(i) {
    const x = Math.sin(i * 999.17 + 4.31) * 43758.5453;
    return x - Math.floor(x);
  }

  // ---------- Shared scientific model (mirrored by the independent Python oracle) ----------
  function kelvin(tC) { return tC + 273.15; }
  function vibAmplitude(tC) { return Math.min(0.3, A0 * Math.sqrt(kelvin(tC) / T_REF)); }
  function kineticRatio(tC) { return kelvin(tC) / T_REF; }
  function escapeFraction(tC, em = 2400) { return Math.exp(-em / (R_GAS * kelvin(tC))); }
  const IONIC_MP = [770, 2572];           // KCl, CaO (lesson anchors, °C).
  const IONIC_NAMES = ["كلوريد البوتاسيوم KCl", "أكسيد الكالسيوم CaO"];
  const MOL_NAMES = ["بلورة اليود I₂", "الجليد H₂O", "كرات باكي C₆₀"];
  const NET_NAMES = ["الماس - رباعي الأوجه", "الغرافيت - طبقات سداسية", "الكوارتز SiO₂"];
  const NET_COORD = [4, 3, 4];
  const NET_HARD = ["الأقسى طبيعيًا", "قاسية (طبقات تنزلق)", "شديدة القساوة"];

  function classifySolid(mp, sigmaS, sigmaM, hardness, brittle) {
    if (sigmaS === 1) return { type: "metallic", rationale: "توصل التيار الكهربائي وهي في الحالة الصلبة؛ وهذه الصفة مميزة للفلزات بفضل بحر الإلكترونات الحرة بين أيوناتها الموجبة." };
    if (sigmaM === 1) return { type: "ionic", rationale: "لا توصل الكهرباء وهي صلبة لكن مصهورها أو محلولها يوصل؛ وهذه الصفة مميزة للمركبات الأيونية، ودرجة انصهارها مرتفعة نسبيًا." };
    if (hardness >= 8 && mp >= 400) return { type: "network", rationale: "شديدة القساوة ودرجة انصهارها مرتفعة ولا توصل الكهرباء ولا مصهورها؛ وهي صفات المواد الشبكية التساهمية ذات الروابط القوية الممتدة." };
    if (mp >= 1500) return { type: "network", rationale: "درجة انصهارها مرتفعة جدًا ولا توصل الكهرباء في أي حالة؛ وهي صفات المواد الشبكية التساهمية." };
    return { type: "molecular", rationale: "درجة انصهارها منخفضة ولا توصل الكهرباء في أي حالة؛ وهي صفات المواد الجزيئية التي تترابط جسيماتها بقوى تجاذب ضعيفة." };
  }
  const TYPE_NAMES = { molecular: "جزيئية", network: "شبكية تساهمية", metallic: "فلزية", ionic: "أيونية" };
  const TYPE_TO_STRUCTURE = { molecular: "iodine", network: "diamond", metallic: "metallic", ionic: "ionic" };

  // ---------- Structure builders (deterministic data, no scene re-initialization) ----------
  function gridAtoms(n, spacing) {
    const atoms = [];
    const start = -spacing * (n - 1) / 2;
    for (let i = 0; i < n; i++) for (let j = 0; j < n; j++) for (let k = 0; k < n; k++) {
      atoms.push({ x: start + i * spacing, y: start + j * spacing, z: start + k * spacing, type: "cation", charge: 0, size: 1 });
    }
    return atoms;
  }
  function nearestBonds(atoms, perAtom, maxDist, kind) {
    const bonds = [];
    const seen = new Set();
    atoms.forEach((a, i) => {
      const dists = atoms.map((b, j) => ({ j, d: Math.hypot(a.x - b.x, a.y - b.y, a.z - b.z) }))
        .filter(o => o.j !== i && o.d <= maxDist).sort((p, q) => p.d - q.d).slice(0, perAtom);
      dists.forEach(o => {
        const key = i < o.j ? `${i}-${o.j}` : `${o.j}-${i}`;
        if (!seen.has(key)) { seen.add(key); bonds.push({ a: i, b: o.j, kind }); }
      });
    });
    return bonds;
  }

  function buildCrystalline() {
    const atoms = gridAtoms(4, 0.34);
    atoms.forEach(a => { a.type = "cryst"; });
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
    const atoms = [];
    const bonds = [];
    const n = 3, s = 0.42;
    let idx = 0;
    const start = -s * (n - 1) / 2;
    const pairCenters = [];
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
      const dists = pairCenters.map((q, qi) => ({ qi, d: Math.hypot(p.x - q.x, p.y - q.y, p.z - q.z) })).filter(o => o.qi !== pi).sort((a2, b2) => a2.d - b2.d).slice(0, 2);
      dists.forEach(o => {
        const key = pi < o.qi ? `${pi}-${o.qi}` : `${o.qi}-${pi}`;
        if (!seen.has(key)) { seen.add(key); bonds.push({ a: pairCenters[pi].i, b: pairCenters[o.qi].i, kind: "weak" }); }
      });
    });
    return { atoms, bonds, coordination: 1 };
  }
  function buildIce() {
    const a = 0.34;
    const base = [
      [-a, -a, -a], [a, -a, -a], [-a, a, -a], [a, a, -a], [-a, -a, a], [a, -a, a], [-a, a, a], [a, a, a],
      [0, -a, 0], [0, a, 0], [-a, 0, 0], [a, 0, 0], [0, 0, -a], [0, 0, a],
      [a / 2, a / 2, a / 2], [-a / 2, -a / 2, a / 2], [-a / 2, a / 2, -a / 2], [a / 2, -a / 2, -a / 2]
    ];
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
    const bonds = nearestBonds(atoms, 3, 0.34, "covalent");
    return { atoms, bonds, coordination: 3, cage: true, euler: { V: 60, E: 90, F: 32, identity: 2 } };
  }
  function buildDiamond() {
    const a = 0.44;
    const pts = [
      [-a, -a, -a], [a, -a, -a], [-a, a, -a], [a, a, -a], [-a, -a, a], [a, -a, a], [-a, a, a], [a, a, a],
      [0, -a, 0], [0, a, 0], [-a, 0, 0], [a, 0, 0], [0, 0, -a], [0, 0, a],
      [a / 2, a / 2, a / 2], [-a / 2, -a / 2, a / 2], [-a / 2, a / 2, -a / 2], [a / 2, -a / 2, -a / 2]
    ];
    const atoms = pts.map(p => ({ x: p[0], y: p[1], z: p[2], type: "carbon", charge: 0, size: 0.92 }));
    const interior = [14, 15, 16, 17];
    const bonds = [];
    interior.forEach(i => {
      const dists = atoms.map((b, j) => ({ j, d: Math.hypot(atoms[i].x - b.x, atoms[i].y - b.y, atoms[i].z - b.z) }))
        .filter(o => o.j !== i).sort((p, q) => p.d - q.d).slice(0, 4);
      dists.forEach(o => bonds.push({ a: i, b: o.j, kind: "covalent" }));
    });
    const seen = new Set();
    const dedup = bonds.filter(b => { const k = b.a < b.b ? `${b.a}-${b.b}` : `${b.b}-${b.a}`; if (seen.has(k)) return false; seen.add(k); return true; });
    return { atoms, bonds: dedup, coordination: 4 };
  }
  function buildGraphite() {
    const atoms = [];
    const b = 0.21;
    const layers = [-0.3, 0, 0.3];
    const layerStart = [];
    layers.forEach((ly, li) => {
      layerStart.push(atoms.length);
      for (let i = 0; i < 3; i++) for (let j = 0; j < 3; j++) {
        const baseX = (i - 1) * 1.5 * b * 2;
        const baseZ = (j - 1) * Math.sqrt(3) * b + (i % 2 ? Math.sqrt(3) / 2 * b : 0);
        atoms.push({ x: baseX, y: ly, z: baseZ, type: "carbon", charge: 0, size: 0.8, layer: li });
        atoms.push({ x: baseX + b, y: ly, z: baseZ, type: "carbon", charge: 0, size: 0.8, layer: li });
      }
    });
    const bonds = [];
    layerStart.forEach((startIdx, li) => {
      const endIdx = li < layerStart.length - 1 ? layerStart[li + 1] : atoms.length;
      const layerAtoms = atoms.slice(startIdx, endIdx);
      layerAtoms.forEach((a2, ii) => {
        const dists = layerAtoms.map((b2, jj) => ({ jj, d: Math.hypot(a2.x - b2.x, a2.z - b2.z) })).filter(o => o.jj !== ii && o.d <= b * 1.15).sort((p, q) => p.d - q.d).slice(0, 3);
        dists.forEach(o => {
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
    const siPositions = [[0, 0, 0], ...outer];
    const atoms = siPositions.map(p => ({ x: p[0], y: p[1], z: p[2], type: "silicon", charge: 0, size: 1 }));
    const siLinks = [];
    for (let i = 1; i <= 4; i++) siLinks.push([0, i]);
    siLinks.push([1, 2], [2, 3], [3, 4], [4, 1]);
    const bonds = [];
    siLinks.forEach(([s1, s2]) => {
      const p1 = atoms[s1], p2 = atoms[s2];
      const ox = (p1.x + p2.x) / 2, oy = (p1.y + p2.y) / 2, oz = (p1.z + p2.z) / 2;
      atoms.push({ x: ox, y: oy, z: oz, type: "oxygenRed", charge: 0, size: 0.62 });
      const oi = atoms.length - 1;
      bonds.push({ a: s1, b: oi, kind: "covalent" });
      bonds.push({ a: s2, b: oi, kind: "covalent" });
    });
    outer.forEach((p, i2) => {
      const dir = Math.hypot(p[0], p[1], p[2]);
      const ox = p[0] + (p[0] / dir) * 0.3, oy = p[1] + (p[1] / dir) * 0.3, oz = p[2] + (p[2] / dir) * 0.3;
      atoms.push({ x: ox, y: oy, z: oz, type: "oxygenRed", charge: 0, size: 0.62 });
      bonds.push({ a: i2 + 1, b: atoms.length - 1, kind: "covalent" });
    });
    return { atoms, bonds, coordination: 4 };
  }
  function buildMetallic() {
    const atoms = [];
    const nx = 4, ny = 3, nz = 4, s = 0.32;
    for (let i = 0; i < nx; i++) for (let j = 0; j < ny; j++) for (let k = 0; k < nz; k++) {
      atoms.push({
        x: (i - (nx - 1) / 2) * s + (j % 2 ? s / 3 : 0),
        y: (j - (ny - 1) / 2) * s,
        z: (k - (nz - 1) / 2) * s + (j % 2 ? s / 3 : 0),
        type: "gold", charge: 1, size: 1.06
      });
    }
    return { atoms, bonds: [], coordination: 12 };
  }
  function buildIonic(material) {
    const atoms = [];
    const n = 4, s = 0.33;
    for (let i = 0; i < n; i++) for (let j = 0; j < n; j++) for (let k = 0; k < n; k++) {
      const positive = (i + j + k) % 2 === 0;
      atoms.push({
        x: (i - (n - 1) / 2) * s,
        y: (j - (n - 1) / 2) * s,
        z: (k - (n - 1) / 2) * s,
        type: material === 0 ? (positive ? "kplus" : "clminus") : (positive ? "caplus" : "ominus"),
        charge: positive ? 1 : -1,
        size: positive ? 0.86 : 1.06
      });
    }
    const bonds = [];
    atoms.forEach((a2, i2) => {
      atoms.forEach((b2, j2) => {
        if (j2 <= i2) return;
        const d = Math.hypot(a2.x - b2.x, a2.y - b2.y, a2.z - b2.z);
        if (Math.abs(d - 0.33) < 0.02 && a2.charge !== b2.charge) bonds.push({ a: i2, b: j2, kind: "ionic" });
      });
    });
    return { atoms, bonds, coordination: 6 };
  }

  const structures = {};
  function getStructure(id) {
    if (id === "ionic") return buildIonic(state.ionMaterial);
    if (!structures[id]) {
      structures[id] = {
        crystalline: buildCrystalline,
        amorphous: buildAmorphous,
        iodine: buildIodine,
        ice: buildIce,
        c60: buildC60,
        diamond: buildDiamond,
        graphite: buildGraphite,
        quartz: buildQuartz,
        metallic: buildMetallic
      }[id]();
    }
    return structures[id];
  }

  // ---------- Persistent atom pool (scene initialized once; structures are data) ----------
  const MAX_ATOMS = 80;
  const atoms = [];
  for (let i = 0; i < MAX_ATOMS; i++) {
    atoms.push({
      active: false, x: 0, y: 0, z: 0, home: { x: 0, y: 0, z: 0 }, from: { x: 0, y: 0, z: 0 },
      slip: { x: 0, y: 0, z: 0 }, type: "cryst", charge: 0, size: 1,
      phase: seededRandom(i * 7 + 3) * Math.PI * 2,
      vx: 0, vy: 0, vz: 0, free: false, morph: 1
    });
  }
  let bonds = [];
  let currentStructureId = "crystalline";
  let currentStructureMeta = getStructure("crystalline");
  let cageRot = 0;
  let moltenActive = false;
  let moltenTransitions = 0;

  function setStructure(id) {
    const s = getStructure(id);
    const targets = s.atoms;
    atoms.forEach((atom, i) => {
      if (i < targets.length) {
        const t = targets[i];
        atom.from = { x: atom.x, y: atom.y, z: atom.z };
        atom.home = { x: t.x, y: t.y, z: t.z };
        atom.slip = { x: 0, y: 0, z: 0 };
        atom.type = t.type; atom.charge = t.charge || 0; atom.size = t.size || 1;
        atom.layer = t.layer;
        atom.active = true; atom.free = false; atom.morph = 0;
        atom.vx = 0; atom.vy = 0; atom.vz = 0;
      } else {
        atom.active = false;
      }
    });
    bonds = s.bonds.map(b => ({ ...b }));
    currentStructureId = id;
    currentStructureMeta = s;
    moltenActive = false;
    metalSlip.progress = 0; metalSlip.done = false;
    ionicSlip.progress = 0; ionicSlip.fractured = false; ionicSlip.repelPairs = []; ionicSlip.gap = 0;
  }

  // ---------- Electrons for the metallic sea (count equals cation charge: the crystal is neutral) ----------
  const electrons = [];
  for (let i = 0; i < 48; i++) {
    electrons.push({
      x: map(seededRandom(i * 11 + 1), 0, 1, -0.8, 0.8),
      y: map(seededRandom(i * 11 + 2), 0, 1, -0.7, 0.7),
      z: map(seededRandom(i * 11 + 3), 0, 1, -0.62, 0.62),
      vx: map(seededRandom(i * 11 + 4), 0, 1, -0.3, 0.3),
      vy: map(seededRandom(i * 11 + 5), 0, 1, -0.3, 0.3),
      vz: map(seededRandom(i * 11 + 6), 0, 1, -0.3, 0.3)
    });
  }
  const ELECTRON_COUNT = electrons.length;

  // ---------- Strike / slip / fracture state ----------
  const metalSlip = { progress: 0, done: false, running: false };
  const ionicSlip = { progress: 0, running: false, fractured: false, repelPairs: [], gap: 0 };

  function activeTemperature() {
    if (state.mode === "properties") return state.temperature;
    if (state.mode === "network") return state.networkTemp;
    if (state.mode === "ionic") return state.ionicTemp;
    return 25;
  }
  function isMolten() {
    if (state.mode === "properties") return state.temperature >= DEMO_MELTING_POINT;
    if (state.mode === "ionic") return state.ionicTemp >= IONIC_MP[state.ionMaterial];
    return false;
  }

  function updateAtoms(dt, dtAnim, now) {
    const T = activeTemperature();
    const amp = vibAmplitude(T);
    const speed = 2.2 + map(clamp(T, -50, 3000), -50, 3000, 0, 7);
    const molten = isMolten();
    if (molten && !moltenActive) {
      atoms.forEach(a2 => { if (a2.active) { a2.free = true; a2.vx = map(seededRandom(a2.phase * 91 + 1), 0, 1, -0.25, 0.25); a2.vy = map(seededRandom(a2.phase * 91 + 2), 0, 1, -0.22, 0.22); a2.vz = map(seededRandom(a2.phase * 91 + 3), 0, 1, -0.25, 0.25); } });
    }
    if (!molten && moltenActive) {
      atoms.forEach(a2 => { if (a2.active) { a2.free = false; a2.from = { x: a2.x, y: a2.y, z: a2.z }; a2.morph = 0; } });
    }
    if (molten !== moltenActive) moltenTransitions++;
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
        const th = 0.8 + map(T, 25, 3000, 0, 1.4);
        a2.vx += Math.sin(now * 0.0013 + a2.phase) * 0.12 * dt * th;
        a2.vy += Math.cos(now * 0.0011 + a2.phase * 1.3) * 0.11 * dt * th;
        a2.vz += Math.sin(now * 0.0009 + a2.phase * 0.7) * 0.12 * dt * th;
        const sp = Math.hypot(a2.vx, a2.vy, a2.vz) || 1;
        const limit = 0.34 + map(T, 25, 3000, 0, 0.3);
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
    const drift = -0.16 * state.field;
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
      if (metalSlip.progress >= 1) { metalSlip.done = true; metalSlip.running = false; updateMetallicUI(); }
    }
    const e = metalSlip.progress * metalSlip.progress * (3 - 2 * metalSlip.progress);
    atoms.forEach(a2 => {
      if (!a2.active || currentStructureId !== "metallic") return;
      if (a2.home.y > 0.05) a2.slip.x = 0.24 * e;
      else a2.slip.x = 0;
    });
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
      if (ionicSlip.gap >= 0.16 && !ionicSlip.fractured) { ionicSlip.fractured = true; updateIonicUI(); }
    }
    const e = ionicSlip.progress * ionicSlip.progress * (3 - 2 * ionicSlip.progress);
    atoms.forEach(a2 => {
      if (!a2.active || currentStructureId !== "ionic") return;
      if (a2.home.y > 0.05) { a2.slip.x = 0.33 * e; a2.slip.y = ionicSlip.gap; }
      else { a2.slip.x = 0; a2.slip.y = -ionicSlip.gap * 0.35; }
    });
  }

  // ---------- Projection and drawing ----------
  function resizeCanvas() {
    const rect = stageShell.getBoundingClientRect();
    width = Math.max(300, Math.round(rect.width));
    height = Math.max(260, Math.round(rect.height));
    dpr = Math.min(2, window.devicePixelRatio || 1);
    const nextW = Math.round(width * dpr);
    const nextH = Math.round(height * dpr);
    if (canvas.width !== nextW || canvas.height !== nextH) {
      canvas.width = nextW;
      canvas.height = nextH;
      canvas.style.width = `${width}px`;
      canvas.style.height = `${height}px`;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    }
  }

  function stageGeometry() {
    const w = Math.min(width * 0.78, 560);
    const h = Math.min(height * 0.62, 360);
    return { cx: width / 2, cy: height * 0.52, halfW: w / 2, halfH: h / 2 };
  }

  function project(p, geometry) {
    const g = geometry || stageGeometry();
    const cosy = Math.cos(rotationY), siny = Math.sin(rotationY);
    const cosx = Math.cos(rotationX), sinx = Math.sin(rotationX);
    const x1 = p.x * cosy - p.z * siny;
    const z1 = p.x * siny + p.z * cosy;
    const y1 = p.y * cosx - z1 * sinx;
    const z2 = p.y * sinx + z1 * cosx;
    const perspective = clamp(1 / (1 + z2 * 0.18), 0.82, 1.18);
    return {
      x: g.cx + (x1 / WORLD.x) * g.halfW * perspective,
      y: g.cy - (y1 / 0.82) * g.halfH * perspective,
      z: z2,
      scale: perspective
    };
  }

  const PALETTES = {
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

  function drawAtom(a2, q) {
    const colors = PALETTES[a2.type] || PALETTES.cryst;
    const r = clamp(9.2 * a2.size * q.scale, 4.5, 16);
    ctx.save();
    ctx.fillStyle = colors[0];
    ctx.beginPath();
    ctx.arc(q.x, q.y, r, 0, Math.PI * 2);
    ctx.fill();
    ctx.strokeStyle = colors[1];
    ctx.lineWidth = Math.max(1, r * 0.12);
    ctx.stroke();
    ctx.globalAlpha = 0.72;
    ctx.fillStyle = "#fff";
    ctx.beginPath();
    ctx.arc(q.x - r * 0.32, q.y - r * 0.34, Math.max(1.2, r * 0.2), 0, Math.PI * 2);
    ctx.fill();
    ctx.globalAlpha = 1;
    if (a2.charge !== 0 && r > 6) {
      ctx.fillStyle = "rgba(255,255,255,.92)";
      ctx.font = `900 ${Math.round(r * 1.05)}px Tahoma`;
      ctx.textAlign = "center";
      ctx.textBaseline = "middle";
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
      ctx.beginPath();
      ctx.moveTo(pa.q.x, pa.q.y);
      ctx.lineTo(pb.q.x, pb.q.y);
      ctx.stroke();
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
      const style = bondStyle("repel");
      ctx.strokeStyle = style.color;
      ctx.lineWidth = style.width;
      ctx.setLineDash(style.dash);
      ctx.globalAlpha = pulse;
      ctx.beginPath();
      ctx.moveTo(pa.q.x, pa.q.y);
      ctx.lineTo(pb.q.x, pb.q.y);
      ctx.stroke();
    });
    ctx.restore();
  }

  function drawElectrons(g) {
    ctx.save();
    electrons.forEach(e2 => {
      const q = project(e2, g);
      ctx.fillStyle = "rgba(126,232,255,.85)";
      ctx.beginPath();
      ctx.arc(q.x, q.y, clamp(2.6 * q.scale, 1.4, 3.4), 0, Math.PI * 2);
      ctx.fill();
    });
    ctx.restore();
  }

  function drawGhostCages(g) {
    ctx.save();
    ctx.globalAlpha = 0.22;
    [[-1.15, -0.5, -0.4], [1.15, 0.5, 0.4]].forEach(off => {
      const meta = getStructure("c60");
      const pts = meta.atoms.map(a2 => project({ x: a2.x * 0.5 + off[0], y: a2.y * 0.5 + off[1], z: a2.z * 0.5 + off[2] }, g));
      pts.forEach(q => {
        ctx.fillStyle = "rgba(150,120,220,.8)";
        ctx.beginPath();
        ctx.arc(q.x, q.y, 3, 0, Math.PI * 2);
        ctx.fill();
      });
    });
    ctx.restore();
  }

  function drawCrackLine(g) {
    if (!ionicSlip.fractured) return;
    ctx.save();
    ctx.strokeStyle = "rgba(255,120,110,.85)";
    ctx.lineWidth = 2.4;
    ctx.setLineDash([7, 5]);
    const y0 = g.cy - (0.1 / 0.82) * g.halfH;
    ctx.beginPath();
    let x = g.cx - g.halfW * 0.9;
    let y = y0;
    ctx.moveTo(x, y);
    for (let i = 1; i <= 12; i++) {
      x = g.cx - g.halfW * 0.9 + (g.halfW * 1.8 * i) / 12;
      y = y0 + (i % 2 ? -9 : 9);
      ctx.lineTo(x, y);
    }
    ctx.stroke();
    ctx.restore();
  }

  function drawScene() {
    ctx.clearRect(0, 0, width, height);
    ctx.fillStyle = "rgba(9,54,82,.16)";
    ctx.fillRect(0, 0, width, height);

    const g = stageGeometry();

    ctx.save();
    ctx.fillStyle = "rgba(6,24,44,.45)";
    ctx.beginPath();
    ctx.ellipse(g.cx, g.cy + g.halfH * 0.92, g.halfW * 0.8, 16, 0, 0, Math.PI * 2);
    ctx.fill();
    ctx.restore();

    let drawList = atoms.filter(a2 => a2.active);
    if (currentStructureId === "c60") {
      const cs = Math.cos(cageRot), sn = Math.sin(cageRot);
      drawList = drawList.map(a2 => {
        const rx = a2.x * cs - a2.z * sn;
        const rz = a2.x * sn + a2.z * cs;
        return { atom: a2, q: project({ x: rx, y: a2.y, z: rz }, g), rot: { x: rx, y: a2.y, z: rz } };
      });
      ctx.save();
      bonds.forEach(b2 => {
        const pa = drawList[b2.a], pb = drawList[b2.b];
        if (!pa || !pb) return;
        ctx.strokeStyle = "rgba(190,160,255,.55)";
        ctx.lineWidth = 1.7;
        ctx.beginPath();
        ctx.moveTo(pa.q.x, pa.q.y);
        ctx.lineTo(pb.q.x, pb.q.y);
        ctx.stroke();
      });
      ctx.restore();
      drawList.sort((p, q2) => p.q.z - q2.q.z).forEach(item => drawAtom(item.atom, item.q));
      drawGhostCages(g);
      return;
    }

    const projected = drawList.map(a2 => ({ atom: a2, q: project(a2, g) }));
    if (currentStructureId === "metallic") drawElectrons(g);
    drawBonds(projected);
    drawRepelPairs(projected);
    projected.sort((p, q2) => p.q.z - q2.q.z);
    projected.forEach(item => drawAtom(item.atom, item.q));
    drawCrackLine(g);
  }

  // ---------- Per-mode structure selection ----------
  function structureForMode() {
    switch (state.mode) {
      case "properties": return state.order === 1 ? "amorphous" : "crystalline";
      case "molecular": return ["iodine", "ice", "c60"][state.molMaterial];
      case "network": return ["diamond", "graphite", "quartz"][state.netMaterial];
      case "metallic": return "metallic";
      case "ionic": return "ionic";
      case "identify": return TYPE_TO_STRUCTURE[classifySolid(state.mp, state.sigmaS, state.sigmaM, state.hardness, state.brittle).type];
      default: return "crystalline";
    }
  }

  function refreshStructure() {
    const id = structureForMode();
    // Ionic data depends on the selected material, so it is always rebuilt when this
    // section's controls change; strikes are guarded against resets while running.
    if (id !== currentStructureId || (id === "ionic" && !ionicSlip.running && ionicSlip.progress === 0)) setStructure(id);
  }

  // ---------- HUD and summary ----------
  function phaseWord() {
    if (state.mode === "properties") return state.temperature >= DEMO_MELTING_POINT ? "منصهرة" : "صلبة - اهتزاز";
    if (state.mode === "ionic") return state.ionicTemp >= IONIC_MP[state.ionMaterial] ? "منصهرة - موصلة" : "صلبة - غير موصلة";
    if (state.mode === "metallic") return state.field > 0 ? "تيار في البلورة" : "بحر إلكترونات";
    if (state.mode === "network") return "بناء شبكي ثابت";
    if (state.mode === "molecular") return "قوى تجاذب ضعيفة";
    return "صلبة - اهتزاز";
  }
  function motifName() {
    switch (currentStructureId) {
      case "crystalline": return "شبكة بلورية";
      case "amorphous": return "غير بلورية";
      case "iodine": return "بلورة يود I₂";
      case "ice": return "جليد رباعي الأوجه";
      case "c60": return "كرة باكي C₆₀";
      case "diamond": return "شبكة الماس";
      case "graphite": return "طبقات الغرافيت";
      case "quartz": return "شبكة الكوارتز";
      case "metallic": return "بلورة فلزية";
      case "ionic": return state.ionMaterial === 0 ? "شبكة KCl" : "شبكة CaO";
      default: return "شبكة بلورية";
    }
  }

  function updateHud() {
    const T = activeTemperature();
    hudTemp.textContent = `${T.toFixed(0)} °C`;
    hudType.textContent = motifName();
    hudState.textContent = phaseWord();
    const metrics = {
      solid: ["جسيمات متقاربة", "حركة اهتزازية"],
      properties: state.order === 1 ? ["ترتيب عشوائي", "اهتزاز في الأماكن"] : ["ترتيب منتظم", "اهتزاز في الأماكن"],
      molecular: ["جزيئات متعادلة", state.molMaterial === 1 ? "روابط هيدروجينية" : "قوى لندن"],
      network: ["روابط تساهمية", `عدد تناسقي ${NET_COORD[state.netMaterial]}`],
      metallic: ["أيونات موجبة", "بحر إلكترونات"],
      ionic: ["أيونات + و −", "شحنة متعادلة"],
      identify: ["خصائص فيزيائية", "توقع النوع"]
    }[state.mode] || ["جسيمات متقاربة", "حركة اهتزازية"];
    hudMetrics.innerHTML = metrics.map(m => `<span><i></i>${m}</span>`).join("");
  }

  function updateSummary(now) {
    if (now - summaryClock < 1600) return;
    summaryClock = now;
    const T = activeTemperature();
    let text;
    if (state.mode === "ionic") {
      text = `شبكة ${IONIC_NAMES[state.ionMaterial]} عند ${T} درجة مئوية؛ درجة الانصهار ${IONIC_MP[state.ionMaterial]}؛ الحالة: ${phaseWord()}؛ الشحنة الكلية صفر.`;
    } else if (state.mode === "metallic") {
      text = `بلورة فلزية؛ شدة المجال ${state.field} من 10؛ التيار النسبي ${(state.field * 0.18).toFixed(2)}؛ عدد الإلكترونات ${ELECTRON_COUNT} محفوظ.`;
    } else if (state.mode === "identify") {
      const c2 = classifySolid(state.mp, state.sigmaS, state.sigmaM, state.hardness, state.brittle);
      text = `مختبر التصنيف: درجة انصهار ${state.mp}، توصيل صلبة ${state.sigmaS ? "نعم" : "لا"}، توصيل مصهورة ${state.sigmaM ? "نعم" : "لا"}؛ النوع المتوقع: ${TYPE_NAMES[c2.type]}.`;
    } else {
      text = `${motifName()} عند ${T} درجة مئوية؛ الحالة: ${phaseWord()}.`;
    }
    simSummary.textContent = text;
  }

  // ---------- UI update functions ----------
  function updatePropertiesUI() {
    $("#temperatureOut").textContent = `${state.temperature} °C`;
    const molten = state.temperature >= DEMO_MELTING_POINT;
    $("#phaseStateOut").textContent = molten ? "منصهرة - غادرت الجسيمات أماكنها" : "صلبة - اهتزاز في الأماكن";
    $("#phaseWordOut").textContent = molten ? "سائلة" : "صلبة";
    $("#kineticOut").textContent = `${kineticRatio(state.temperature).toFixed(2)} ×`;
    $("#propertiesInvariant").textContent = molten
      ? `عند ${state.temperature} °C ≥ درجة الانصهار (${DEMO_MELTING_POINT} °C): زادت الطاقة الحركية حتى ضعف التجاذب فغادرت الجسيمات أماكنها وتحولت المادة إلى سائل.`
      : `عند ${state.temperature} °C < درجة الانصهار (${DEMO_MELTING_POINT} °C): تهتز الجسيمات حول مواضعها ولا تغادرها، ومتوسط طاقتها الحركية ${kineticRatio(state.temperature).toFixed(2)} ضعف قيمته عند 25 °C (يتناسب مع T بالكلفن).`;
    $$("[data-order]").forEach(b2 => b2.classList.toggle("active", Number(b2.dataset.order) === state.order));
    updateHud();
    window.__SCIENCE_DEBUG__.scientificUpdates++;
  }

  function updateMolecularUI() {
    $("#molecularMaterialOut").textContent = MOL_NAMES[state.molMaterial];
    $("#attractionOut").textContent = `${state.attraction} / 10`;
    $("#forceKindOut").textContent = state.molMaterial === 1 ? "روابط هيدروجينية" : "قوى لندن";
    const words = state.attraction >= 8 ? "مرتفعة نسبيًا" : state.attraction >= 5 ? "متوسطة" : state.attraction >= 3 ? "منخفضة" : "منخفضة جدًا";
    $("#mpEstimateOut").textContent = words;
    $("#molecularInvariant").textContent = state.molMaterial === 2
      ? "جزيء C₆₀ يحقق معادلة أويلر: 60 رأسًا − 90 ضلعًا + 32 وجهًا = 2 (12 خماسيًا و20 سداسيًا)، وترتبط كل ذرة كربون بثلاث ذرات بروابط تساهمية، والجزيئات متعادلة فلا توصل الكهرباء."
      : state.molMaterial === 1
        ? "كل جزيء ماء في الجليد مرتبط بأربعة جزيئات أخرى بروابط هيدروجينية، وكل جزيء مركز لرباعي أوجه منتظم؛ والجزيئات متعادلة فلا توصل الكهرباء."
        : `قوة التجاذب ${state.attraction}/10: كلما قويت قوى التجاذب بين الجزيئات ارتفعت درجة الانصهار المتوقعة (${words})؛ والجزيئات متعادلة الشحنة فلا توصل الكهرباء.`;
    $$("[data-mat]").forEach(b2 => b2.classList.toggle("active", Number(b2.dataset.mat) === state.molMaterial));
    updateHud();
    window.__SCIENCE_DEBUG__.scientificUpdates++;
  }

  function updateNetworkUI() {
    $("#networkMaterialOut").textContent = NET_NAMES[state.netMaterial];
    $("#networkTempOut").textContent = `${state.networkTemp} °C`;
    $("#coordinationOut").textContent = `${NET_COORD[state.netMaterial]}`;
    $("#hardnessWordOut").textContent = NET_HARD[state.netMaterial];
    $("#networkConductOut").textContent = state.netMaterial === 1 ? "موصلة على امتداد الطبقات (استثناء)" : "غير موصلة";
    $("#networkInvariant").textContent = `الروابط التساهمية في ${["الماس", "الغرافيت", "الكوارتز"][state.netMaterial]} لا تنفصل بالاهتزاز الحراري عند ${state.networkTemp} °C ضمن مجال العرض، والعدد التناسقي ثابت (${NET_COORD[state.netMaterial]}).`;
    $$("[data-net]").forEach(b2 => b2.classList.toggle("active", Number(b2.dataset.net) === state.netMaterial));
    updateHud();
    window.__SCIENCE_DEBUG__.scientificUpdates++;
  }

  function updateMetallicUI() {
    $("#fieldOut").textContent = `${state.field} / 10`;
    $("#currentOut").textContent = `التيار النسبي: ${(state.field * 0.18).toFixed(2)}`;
    $("#slipStateOut").textContent = metalSlip.done ? "انزلقت وبقيت مترابطة" : "الصفوف تنزلق وتبقى مترابطة";
    $("#metallicInvariant").textContent = `عدد الإلكترونات في البحر محفوظ (${ELECTRON_COUNT})، والبلورة متعادلة الشحنة (${atoms.filter(a2 => a2.active && a2.type === "gold").length} أيونًا موجبًا تعادلها ${ELECTRON_COUNT} إلكترونًا حرًا)؛ والطرق يزلق الصفوف دون قطع الرابطة.`;
    updateHud();
    window.__SCIENCE_DEBUG__.scientificUpdates++;
  }

  function updateIonicUI() {
    const mp = IONIC_MP[state.ionMaterial];
    const molten = state.ionicTemp >= mp;
    $("#ionicTempOut").textContent = `${state.ionicTemp} °C`;
    $("#ionicMpOut").textContent = `${mp} °C`;
    $("#ionicStateOut").textContent = molten ? "منصهرة - الأيونات حرة" : ionicSlip.fractured ? "تحطمت البلورة" : "صلبة - غير موصلة";
    $("#ionicConductOut").textContent = molten ? "موصلة (مصهور)" : "غير موصلة (صلبة)";
    $("#fractureStateOut").textContent = molten ? "لا تتحطم وهي منصهرة" : ionicSlip.fractured ? "تحطمت (هشة)" : "تتحطم (هشة)";
    $("#ionicInvariant").textContent = molten
      ? `عند ${state.ionicTemp} °C ≥ ${mp} °C: أصبحت الأيونات حرة الحركة فتوصل الكهرباء، والشحنة الكلية تبقى صفرًا.`
      : ionicSlip.fractured
        ? `الطرق أزلق المستويات فتقاربت ${ionicSlip.repelPairs.length} أزواج من الأيونات المتشابهة في الشحنة وتنافرت؛ فتحطمت البلورة رغم صلابتها.`
        : `عند ${state.ionicTemp} °C < ${mp} °C: الأيونات مثبتة في الشبكة المتعادلة فلا توصل الكهرباء؛ والطرق يزلق المستويات فيقارب المتشابهة فتتحطم البلورة.`;
    $$("[data-ion]").forEach(b2 => b2.classList.toggle("active", Number(b2.dataset.ion) === state.ionMaterial));
    updateHud();
    window.__SCIENCE_DEBUG__.scientificUpdates++;
  }

  function updateIdentifyUI() {
    $("#mpOut").textContent = `${state.mp} °C`;
    $("#hardnessOut").textContent = `${state.hardness} / 10`;
    const c2 = classifySolid(state.mp, state.sigmaS, state.sigmaM, state.hardness, state.brittle);
    $("#predictedTypeOut").textContent = TYPE_NAMES[c2.type];
    $("#classifyRationale").textContent = c2.rationale;
    $$("[data-cs]").forEach(b2 => b2.classList.toggle("active", Number(b2.dataset.cs) === state.sigmaS));
    $$("[data-cm]").forEach(b2 => b2.classList.toggle("active", Number(b2.dataset.cm) === state.sigmaM));
    $$("[data-br]").forEach(b2 => b2.classList.toggle("active", Number(b2.dataset.br) === state.brittle));
    updateHud();
    window.__SCIENCE_DEBUG__.scientificUpdates++;
  }

  const PRESETS = {
    ex11a: { mp: 730, sigmaS: 0, sigmaM: 1, hardness: 6, brittle: 1 },
    ex11b: { mp: 3000, sigmaS: 0, sigmaM: 0, hardness: 10, brittle: 0 },
    q5a: { mp: 650, sigmaS: 0, sigmaM: 1, hardness: 6, brittle: 1 },
    q5b: { mp: 900, sigmaS: 1, sigmaM: 1, hardness: 5, brittle: 0 },
    q5c: { mp: 2730, sigmaS: 0, sigmaM: 0, hardness: 10, brittle: 0 },
    q5d: { mp: 119, sigmaS: 0, sigmaM: 0, hardness: 2, brittle: 0 }
  };

  // ---------- Mode / section machinery ----------
  function setMode(section) {
    if (!section) return;
    const mode = section.dataset.mode || "solid";
    if (state.mode !== mode) {
      state.mode = mode;
      window.__SCIENCE_DEBUG__.sectionModeChanges++;
      window.__SCIENCE_DEBUG__.lastMode = mode;
      targetRotationX = clamp(targetRotationX, -0.24, 0.24);
    }
    activeSection = section;
    refreshStructure();
    const morphable = atoms.some(a2 => a2.active && a2.morph < 1);
    atoms.forEach(a2 => { if (a2.active && a2.morph < 1) { a2.from = { x: a2.home.x, y: a2.home.y, z: a2.home.z }; a2.morph = 1; } });
    if (morphable) window.__SCIENCE_DEBUG__.scientificUpdates++;
    stageTitle.textContent = section.dataset.title || "الحالة الصلبة";
    stageKicker.textContent = section.dataset.kicker || "تجربة تعليمية تفاعلية";
    updateHud();
    $$("#sectionRail a").forEach(a2 => a2.classList.toggle("active", a2.getAttribute("href") === `#${section.id}`));
  }

  function moveStage(forceHero = null) {
    const shouldHero = forceHero === null ? window.scrollY < hero.offsetHeight * 0.58 : forceHero;
    if (shouldHero && !stageInHero) {
      heroVisual.appendChild(stageShell);
      stageShell.classList.add("hero-stage-shell");
      stageInHero = true;
      requestAnimationFrame(resizeCanvas);
    } else if (!shouldHero && stageInHero) {
      stickyStage.appendChild(stageShell);
      stageShell.classList.remove("hero-stage-shell");
      stageInHero = false;
      requestAnimationFrame(resizeCanvas);
    }
  }

  function updateProgress() {
    const scrollable = document.documentElement.scrollHeight - innerHeight;
    $("#readingProgress").style.width = `${scrollable > 0 ? clamp(scrollY / scrollable * 100, 0, 100) : 0}%`;
    $("#topbar").classList.toggle("scrolled", scrollY > 18);
    moveStage();
  }

  // ---------- Main loop (single persistent loop) ----------
  function render(now) {
    const dtReal = (now - lastTime) / 1000 || 0.016;
    lastTime = now;
    // dt drives per-frame physics (clamped small for stability); dtAnim drives
    // one-shot transitions so they finish in real time even on throttled frames.
    const dt = Math.min(0.033, dtReal);
    const dtAnim = Math.min(0.3, dtReal);
    rotationY = lerp(rotationY, targetRotationY, 0.08);
    rotationX = lerp(rotationX, targetRotationX, 0.08);
    if (!state.paused) {
      if (currentStructureId === "c60") cageRot += dt * 0.5;
      updateAtoms(dt, dtAnim, now);
      if (currentStructureId === "metallic") updateElectrons(dt, now);
      if (currentStructureId === "metallic") updateMetalSlip(dtAnim);
      if (currentStructureId === "ionic") updateIonicSlip(dtAnim);
    }
    drawScene();
    updateSummary(now);
    window.__SCIENCE_DEBUG__.frameCount++;
    requestAnimationFrame(render);
  }

  // ---------- Controls ----------
  function setupControls() {
    $("#temperatureControl").addEventListener("input", e2 => {
      state.temperature = clamp(Number(e2.target.value) || 25, -50, 1400);
      updatePropertiesUI();
    });
    $$("[data-order]").forEach(btn => btn.addEventListener("click", () => {
      state.order = Number(btn.dataset.order);
      refreshStructure();
      updatePropertiesUI();
    }));
    $$("[data-mat]").forEach(btn => btn.addEventListener("click", () => {
      state.molMaterial = Number(btn.dataset.mat);
      refreshStructure();
      updateMolecularUI();
    }));
    $("#attractionControl").addEventListener("input", e2 => {
      state.attraction = clamp(Number(e2.target.value) || 3, 1, 10);
      updateMolecularUI();
    });
    $$("[data-net]").forEach(btn => btn.addEventListener("click", () => {
      state.netMaterial = Number(btn.dataset.net);
      refreshStructure();
      updateNetworkUI();
    }));
    $("#networkTempControl").addEventListener("input", e2 => {
      state.networkTemp = clamp(Number(e2.target.value) || 25, 25, 3000);
      updateNetworkUI();
    });
    $("#fieldControl").addEventListener("input", e2 => {
      state.field = clamp(Number(e2.target.value) || 0, 0, 10);
      updateMetallicUI();
    });
    $("#strikeMetal").addEventListener("click", () => {
      if (currentStructureId !== "metallic") setStructure("metallic");
      metalSlip.progress = 0; metalSlip.done = false; metalSlip.running = true;
      updateMetallicUI();
    });
    $("#restoreMetal").addEventListener("click", () => {
      metalSlip.progress = 0; metalSlip.done = false; metalSlip.running = false;
      atoms.forEach(a2 => { a2.slip = { x: 0, y: 0, z: 0 }; });
      updateMetallicUI();
    });
    $$("[data-ion]").forEach(btn => btn.addEventListener("click", () => {
      state.ionMaterial = Number(btn.dataset.ion);
      setStructure("ionic");
      updateIonicUI();
    }));
    $("#ionicTempControl").addEventListener("input", e2 => {
      state.ionicTemp = clamp(Number(e2.target.value) || 25, 25, 2600);
      updateIonicUI();
    });
    $("#strikeIonic").addEventListener("click", () => {
      if (state.ionicTemp >= IONIC_MP[state.ionMaterial]) { updateIonicUI(); return; }
      if (currentStructureId !== "ionic") setStructure("ionic");
      ionicSlip.progress = 0; ionicSlip.running = true; ionicSlip.fractured = false; ionicSlip.repelPairs = []; ionicSlip.gap = 0;
      updateIonicUI();
    });
    $("#restoreIonic").addEventListener("click", () => {
      ionicSlip.progress = 0; ionicSlip.running = false; ionicSlip.fractured = false; ionicSlip.repelPairs = []; ionicSlip.gap = 0;
      atoms.forEach(a2 => { a2.slip = { x: 0, y: 0, z: 0 }; });
      updateIonicUI();
    });
    $("#mpControl").addEventListener("input", e2 => {
      state.mp = clamp(Number(e2.target.value) || 0, 0, 3000);
      refreshStructure();
      updateIdentifyUI();
    });
    $("#hardnessControl").addEventListener("input", e2 => {
      state.hardness = clamp(Number(e2.target.value) || 1, 1, 10);
      refreshStructure();
      updateIdentifyUI();
    });
    $$("[data-cs]").forEach(btn => btn.addEventListener("click", () => { state.sigmaS = Number(btn.dataset.cs); refreshStructure(); updateIdentifyUI(); }));
    $$("[data-cm]").forEach(btn => btn.addEventListener("click", () => { state.sigmaM = Number(btn.dataset.cm); refreshStructure(); updateIdentifyUI(); }));
    $$("[data-br]").forEach(btn => btn.addEventListener("click", () => { state.brittle = Number(btn.dataset.br); updateIdentifyUI(); }));
    $$("[data-preset]").forEach(btn => btn.addEventListener("click", () => {
      const p = PRESETS[btn.dataset.preset];
      if (!p) return;
      Object.assign(state, p);
      $("#mpControl").value = state.mp;
      $("#hardnessControl").value = state.hardness;
      refreshStructure();
      updateIdentifyUI();
    }));
    $("#motionToggle").addEventListener("click", () => {
      state.paused = !state.paused;
      document.body.classList.toggle("motion-paused", state.paused);
      $("#motionToggle").setAttribute("aria-label", state.paused ? "تشغيل الحركة" : "إيقاف الحركة");
    });
    fullscreenToggle.addEventListener("click", async () => {
      if (document.fullscreenElement) {
        await document.exitFullscreen();
      } else if (stageShell.requestFullscreen) {
        await stageShell.requestFullscreen();
      } else {
        stageShell.classList.toggle("pseudo-fullscreen");
      }
      requestAnimationFrame(resizeCanvas);
    });
    document.addEventListener("fullscreenchange", () => {
      const active = document.fullscreenElement === stageShell || stageShell.classList.contains("pseudo-fullscreen");
      fullscreenToggle.setAttribute("aria-label", active ? "إنهاء عرض ملء الشاشة" : "عرض المحاكاة بملء الشاشة");
      fullscreenToggle.querySelector("span").textContent = active ? "إنهاء ملء الشاشة" : "ملء الشاشة";
      requestAnimationFrame(resizeCanvas);
    });
    mobileNavToggle.addEventListener("click", () => {
      const open = document.body.classList.toggle("mobile-nav-open");
      mobileNavToggle.setAttribute("aria-expanded", String(open));
      mobileNavToggle.setAttribute("aria-label", open ? "إغلاق قائمة أقسام الدرس" : "فتح قائمة أقسام الدرس");
    });
    $$("a", mobileNav).forEach(link => link.addEventListener("click", () => {
      document.body.classList.remove("mobile-nav-open");
      mobileNavToggle.setAttribute("aria-expanded", "false");
      mobileNavToggle.setAttribute("aria-label", "فتح قائمة أقسام الدرس");
    }));
    stageCollapseToggle.addEventListener("click", () => {
      const collapsed = stickyStage.classList.toggle("collapsed");
      stageCollapseToggle.setAttribute("aria-expanded", String(!collapsed));
      stageCollapseToggle.textContent = collapsed ? "عرض المجسم" : "طي المجسم";
      if (!collapsed) requestAnimationFrame(resizeCanvas);
    });
    document.addEventListener("keydown", event => {
      if (event.key === "Escape" && document.body.classList.contains("mobile-nav-open")) {
        document.body.classList.remove("mobile-nav-open");
        mobileNavToggle.setAttribute("aria-expanded", "false");
      }
    });
    $("#resetAll").addEventListener("click", resetAll);
  }

  function resetAll() {
    Object.assign(state, defaults);
    setStructure("crystalline");
    state.mode = hero.dataset.mode;
    activeSection = hero;
    electrons.forEach((e2, i) => {
      e2.x = map(seededRandom(i * 11 + 1), 0, 1, -0.8, 0.8);
      e2.y = map(seededRandom(i * 11 + 2), 0, 1, -0.7, 0.7);
      e2.z = map(seededRandom(i * 11 + 3), 0, 1, -0.62, 0.62);
    });
    $("#temperatureControl").value = state.temperature;
    $("#attractionControl").value = state.attraction;
    $("#networkTempControl").value = state.networkTemp;
    $("#fieldControl").value = state.field;
    $("#ionicTempControl").value = state.ionicTemp;
    $("#mpControl").value = state.mp;
    $("#hardnessControl").value = state.hardness;
    updatePropertiesUI(); updateMolecularUI(); updateNetworkUI(); updateMetallicUI(); updateIonicUI(); updateIdentifyUI();
    updateHud();
  }

  // ---------- Quiz ----------
  const quizExplanations = {
    q1: "جسيمات الصلبة متقاربة جدًا وقوى التجاذب بينها كبيرة، فهي مثبتة في أماكنها تهتز فقط؛ لذلك شكلها وحجمها ثابتان.",
    q2: "المادة غير البلورية جسيماتها مترتبة عشوائيًا وليس لها شكل هندسي منتظم، مثل الزجاج والبلاستيك.",
    q3: "داخل الجزيء ترتبط كل ذرة كربون بثلاث ذرات بروابط تساهمية، أما بين الجزيئات (الكرات) فتسود قوى لندن الضعيفة.",
    q4: "KCl مركب أيوني: صلب وهش ودرجة انصهاره مرتفعة (770 °C)؛ أما الماس فشديد الصلابة دون أن يوصف بالهشاشة هنا، وCu فلز قابل للطرق، وSiF4 مادة جزيئية.",
    q5: "حلقات جزيء C₆₀ خماسية وسداسية معًا وتشبه كرة القدم؛ أما وصف (حلقات سداسية مرتبطة ببعضها) فهو من صفات الغرافيت.",
    q6: "MgO مركب أيوني درجة انصهاره مرتفعة جدًا، بينما NO₂ وCl₂O وSO₃ مواد جزيئية قوى التجاذب بين جزيئاتها ضعيفة فدرجات انصهارها منخفضة.",
    q7: "P₄ يتكون من جزيئات متعادلة تترابط بقوى تجاذب ضعيفة؛ أما Al ففلز، وBaCl₂ مركب أيوني، وSi مادة شبكية تساهمية.",
    q8: "شدة الصلابة مع درجة انصهار مرتفعة جدًا وعدم توصيل المصهور للكهرباء صفات المواد الشبكية التساهمية."
  };
  function setupQuiz() {
    $("#quizForm").addEventListener("submit", e2 => {
      e2.preventDefault();
      let score = 0, total = 0;
      $$("#quizForm fieldset").forEach((fs, i) => {
        total++;
        const selected = $("input:checked", fs);
        const correct = selected && selected.value === fs.dataset.answer;
        fs.classList.toggle("correct", !!correct);
        fs.classList.toggle("incorrect", !correct);
        if (correct) score++;
        const f = $(".quiz-feedback", fs);
        f.textContent = `${correct ? "إجابة صحيحة." : "إجابة غير صحيحة."} ${quizExplanations[`q${i + 1}`]}`;
      });
      $("#quizScore").textContent = `النتيجة: ${score} / ${total}`;
      window.__SCIENCE_DEBUG__.scientificUpdates++;
    });
    $("#resetQuiz").addEventListener("click", () => {
      $("#quizForm").reset();
      $$("#quizForm fieldset").forEach(fs => fs.classList.remove("correct", "incorrect"));
      $("#quizScore").textContent = "لم يتم التصحيح بعد";
    });
  }

  // ---------- Observers / interaction / demo ----------
  function setupObservers() {
    const sections = [hero, ...$$(".content-section")];
    const obs = new IntersectionObserver(entries => {
      const visible = entries.filter(e2 => e2.isIntersecting).sort((a2, b2) => b2.intersectionRatio - a2.intersectionRatio)[0];
      if (visible) setMode(visible.target);
    }, { rootMargin: "-25% 0px -48% 0px", threshold: [0, 0.15, 0.35, 0.6] });
    sections.forEach(s2 => obs.observe(s2));
    window.addEventListener("scroll", updateProgress, { passive: true });
    window.addEventListener("resize", () => { resizeCanvas(); updateProgress(); });
  }

  function setupCanvasInteraction() {
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
      dragging = false;
      pointerStart = null;
      if (canvas.hasPointerCapture?.(e2.pointerId)) canvas.releasePointerCapture(e2.pointerId);
    };
    canvas.addEventListener("pointerup", end);
    canvas.addEventListener("pointercancel", end);
  }

  function setupHeroDemo() {
    $("#heroDemo").addEventListener("click", async () => {
      for (const id of ["properties", "molecular", "network", "metallic", "ionic", "identify"]) {
        const section = $(`#${id}`);
        if (!section) continue;
        section.scrollIntoView({ behavior: "smooth", block: "center" });
        await new Promise(r2 => setTimeout(r2, 900));
      }
    });
  }

  // ---------- Test snapshot of the scientific model ----------
  window.__SCIENCE_MODEL__ = {
    probeAtoms() {
      return atoms.filter(a2 => a2.active).map((a2, i) => ({
        i, type: a2.type, morph: +a2.morph.toFixed(3), free: a2.free,
        dispHome: +Math.hypot(a2.x - a2.home.x - a2.slip.x, a2.y - a2.home.y - a2.slip.y, a2.z - a2.home.z - a2.slip.z).toFixed(4),
        fromHome: +Math.hypot(a2.from.x - a2.home.x, a2.from.y - a2.home.y, a2.from.z - a2.home.z).toFixed(4),
        pos: [+a2.x.toFixed(3), +a2.y.toFixed(3), +a2.z.toFixed(3)],
        home: [+a2.home.x.toFixed(3), +a2.home.y.toFixed(3), +a2.home.z.toFixed(3)]
      })).sort((p, q) => q.dispHome - p.dispHome).slice(0, 6);
    },
    snapshot() {
      const T = activeTemperature();
      const amp = vibAmplitude(T);
      let maxDisplacement = 0;
      let allInside = true;
      const activeAtoms = atoms.filter(a2 => a2.active);
      const midMorph = activeAtoms.some(a2 => a2.morph < 1);
      activeAtoms.forEach(a2 => {
        if (!a2.free && a2.morph >= 1) {
          const dx = a2.x - (a2.home.x + a2.slip.x);
          const dy = a2.y - (a2.home.y + a2.slip.y);
          const dz = a2.z - (a2.home.z + a2.slip.z);
          maxDisplacement = Math.max(maxDisplacement, Math.hypot(dx, dy, dz));
        }
        if (Math.abs(a2.x) > WORLD.x + 0.001 || a2.y > WORLD.yTop + 0.001 || a2.y < WORLD.yBottom - 0.001 || Math.abs(a2.z) > WORLD.z + 0.001) allInside = false;
      });
      const chargeSum = activeAtoms.reduce((s2, a2) => s2 + a2.charge, 0);
      const goldCount = activeAtoms.filter(a2 => a2.type === "gold").length;
      const isMetallicView = currentStructureId === "metallic";
      const neutral = isMetallicView ? goldCount === electrons.length : chargeSum === 0;
      const c60meta = getStructure("c60");
      const c2 = classifySolid(state.mp, state.sigmaS, state.sigmaM, state.hardness, state.brittle);
      return {
        mode: state.mode,
        coordinateConvention: "world-y-up",
        structureId: currentStructureId,
        activeAtomCount: activeAtoms.length,
        bondCount: bonds.length,
        temperature: T,
        temperatureKelvin: kelvin(T),
        amplitude: amp,
        expectedAmplitudeBound: amp * Math.sqrt(3) * 1.01 + 1e-6,
        maxDisplacementFromHome: maxDisplacement,
        structureMorphing: midMorph,
        atomsWithinExpectedAmplitude: midMorph ? true : maxDisplacement <= amp * Math.sqrt(3) * 1.01 + 1e-6,
        molten: moltenActive,
        moltenTransitions,
        atomsInsideWorldBounds: allInside,
        chargeSum,
        cationCount: goldCount,
        chargeNeutral: neutral,
        electronCount: electrons.length,
        electronCountConserved: electrons.length === ELECTRON_COUNT,
        currentRelative: state.field * 0.18,
        metalSlipProgress: metalSlip.progress,
        metalSlipDone: metalSlip.done,
        ionicSlipProgress: ionicSlip.progress,
        ionicFractured: ionicSlip.fractured,
        ionicRepelPairCount: ionicSlip.repelPairs.length,
        ionicMeltingPoint: IONIC_MP[state.ionMaterial],
        ionicConducts: state.ionicTemp >= IONIC_MP[state.ionMaterial],
        networkCoordination: currentStructureMeta.coordination,
        c60Euler: { ...c60meta.euler, holds: c60meta.euler.V - c60meta.euler.E + c60meta.euler.F === 2 },
        escapeFractionAtT: escapeFraction(T),
        kineticRatioAtT: kineticRatio(T),
        classification: { mp: state.mp, sigmaS: state.sigmaS, sigmaM: state.sigmaM, hardness: state.hardness, brittle: state.brittle, predicted: c2.type },
        canvasCounts: {
          sceneInit: window.__SCIENCE_DEBUG__.sceneInitCount["solid-state"],
          rendererCreate: window.__SCIENCE_DEBUG__.rendererCreateCount["solid-state"],
          loops: window.__SCIENCE_DEBUG__.activeAnimationLoops
        }
      };
    }
  };

  function init() {
    setStructure("crystalline");
    resizeCanvas();
    setupControls();
    setupQuiz();
    setupObservers();
    setupCanvasInteraction();
    setupHeroDemo();
    updatePropertiesUI();
    updateMolecularUI();
    updateNetworkUI();
    updateMetallicUI();
    updateIonicUI();
    updateIdentifyUI();
    updateProgress();
    updateHud();
    requestAnimationFrame(render);
  }

  init();
})();
