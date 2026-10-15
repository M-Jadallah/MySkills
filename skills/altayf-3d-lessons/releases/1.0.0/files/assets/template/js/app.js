/* app.js — lesson wiring. Rewrite this file per lesson; engine.js stays untouched.
 * Skeleton shows every hook you need. See references/stage-engine.md for the full API
 * and assets/example-solid-state/app.js for a complete proven lesson.
 */
"use strict";

/* ---------- 1. create the stage ---------- */
const stage = createStage({
  canvas: "#solidCanvas",
  shell: "#stageShell",
  heroVisual: ".hero-visual",
  sticky: "#stickyStage",
  hero: "#hero",
  rail: "#sectionRail",
  hud: {
    title: "#stageTitle", kicker: "#stageKicker", metrics: "#hudMetrics",
    temp: "#hudTemp", type: "#hudType", state: "#hudState", summary: "#simSummary",
  },
});

/* ---------- 2. lesson state ---------- */
const state = {
  mode: "solid",
  // TODO: lesson variables, e.g. material: 0, order: 0, attraction: 3 …
};
stage.state = state;

/* ---------- 3. custom structures & palettes (optional) ---------- */
// Stock structures already available: crystalline, amorphous, iodine, ice, c60,
// diamond, graphite, quartz, metallic (electron sea), ionic (uses state.ionMaterial).
// Add custom ones:
// stage.palettes.myAtom = ["#0b2a49", "rgba(90,200,255,.95)"];
// stage.registerStructure("myStructure", (st) => {
//   const atoms = st.utils.gridAtoms(3, 0.36, "myAtom");
//   return { atoms, bonds: st.utils.nearestBonds(atoms, 3, 0.4, "covalent"), coordination: 6 };
// });

/* ---------- 4. section → structure mapping ---------- */
const MODE_STRUCTURES = {
  // TODO: map each section's data-mode to a structure id, e.g.
  // properties: () => state.order === 1 ? "amorphous" : "crystalline",
};
function structureForMode() {
  const resolver = MODE_STRUCTURES[state.mode];
  return resolver ? resolver() : "crystalline";
}

/* ---------- 5. HUD ---------- */
function updateHud() {
  // TODO: metrics chips + live metrics per mode (see example lesson).
  stage.updateHud({
    metrics: ["…", "…"],
    type: "…",   // motif name (e.g. "شبكة بلورية")
    state: "…",  // phase word (e.g. "صلبة - اهتزاز")
  });
}
stage.setSummaryProvider((st) => `… ${st.temperature()} °C …`);

/* ---------- 6. control panels ---------- */
function setupControls() {
  // TODO per interaction-panel:
  // bindRange("#temperatureControl", (v) => { state.temperature = v; stage.setTemperature(v); updateHud(); });
  // bindSegmented("[data-mat]", (btn) => { state.material = Number(btn.dataset.mat); setActive("[data-mat]", b => b === btn); stage.rebuild(); updateHud(); });
  // Strikes: stage.strikeMetallic() / stage.strikeIonic() / stage.restoreStrikes();
  //   stage.onSlipDone = (kind) => { …update evidence text… };
  $("#resetAll")?.addEventListener("click", () => stage.reset("crystalline", () => { /* reset state + inputs + UI */ }));
  $("#heroDemo")?.addEventListener("click", () => stage.tour([/* section ids */]));
}

/* ---------- 7. quiz ---------- */
const quizExplanations = {
  // q1: "…", q2: "…"  (keyed by input name)
};

/* ---------- 8. init ---------- */
stage.setTemperature(25);
// stage.setMeltingPoint(800); // number, or (st) => MPs[st.state.material]
setupControls();
initQuiz({ explanations: quizExplanations });
stage.observeSections((section, st) => {
  state.mode = section.dataset.mode || "solid";
  st.show(structureForMode());
  updateHud();
});
updateHud();
stage.start("crystalline");
