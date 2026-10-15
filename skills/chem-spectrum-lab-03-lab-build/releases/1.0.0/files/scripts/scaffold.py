#!/usr/bin/env python3
"""Chem Spectrum Lab - Step 03 scaffold generator.

Creates a standalone single-lesson lab folder under a frontend repo, applying
the "مختبر الطيف للكيمياء" brand identity. Vanilla HTML/CSS/JS only.

Usage:
    python scaffold.py --lesson XX --title "عنوان الدرس" \
        --design "<path>/design-XX.md" --root "<path>/frontend" [--docker]

Flags:
    --docker   also copy the Docker files into <root>/../docker and the repo
               root compose file. Use ONLY for the first lesson.
"""
import argparse, os, pathlib, shutil, sys

SKILL_DIR = pathlib.Path(__file__).resolve().parent.parent
DOCKER_SRC = SKILL_DIR / "references" / "docker"

BRAND = {
    "primary": "#00D4FF",
    "secondary": "#1A237E",
    "white": "#FFFFFF",
    "bg_dark": "#0A0E27",
    "bg_light": "#F5F7FA",
    "teacher": "م. معتصم جادالله (مهندس) — مدرس كيمياء",
    "phone": "0788521514",
    "whatsapp": "+962 78 852 1514",
    "lab_name": "مختبر الطيف للكيمياء",
}


def logo_svg():
    # Inline fallback logo: flask + spectrum wave, brand colors.
    return f'''<svg class="logo-fallback" viewBox="0 0 120 120" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="{BRAND['lab_name']}">
  <path d="M50 20 h20 v20 l18 40 a8 8 0 0 1-7 12 H39 a8 8 0 0 1-7-12 l18-40 Z" fill="none" stroke="{BRAND['primary']}" stroke-width="4"/>
  <path d="M40 60 h40" stroke="{BRAND['white']}" stroke-width="3"/>
  <path d="M10 95 q15 -20 30 0 t30 0 t30 0" fill="none" stroke="{BRAND['primary']}" stroke-width="4" opacity="0.8"/>
</svg>'''


def gen_index_html(title, lesson):
    return f'''<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
  <title>{BRAND['lab_name']} — {title}</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link href="https://fonts.googleapis.com/css2?family=Noto+Kufi+Arabic:wght@400;700&family=Inter:wght@400;600&display=swap" rel="stylesheet">
  <link rel="stylesheet" href="css/lab-style.css">
  <!-- هوية موحّدة: نرث الرأس/التذييل/التخزين/التنقّل من shared المشترك -->
  <link rel="stylesheet" href="../../shared/theme.css">
  <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js" defer></script>
  <script src="../../shared/storage.js" defer></script>
  <script src="../../shared/layout.js" defer></script>
  <script src="../../shared/nav.js" defer></script>
  <script src="../../shared/device.js" defer></script>
  <script src="../../shared/fx.js" defer></script>
  <script src="js/molecules.js" defer></script>
  <script src="js/charts.js" defer></script>
  <script src="js/experiment.js" defer></script>
  <!-- بيانات الدروس (يحتاجها nav.js للتنقّل سابق/تالي) -->
  <script src="../../shared/lessons-data.js"></script>
</head>
<body>
  <!-- الرأس الموحّد (يملؤه layout.js من shared) -->
  <div id="site-header"></div>

  <!-- 1. شاشة البداية -->
  <section id="start-screen" class="screen">
    <header class="brand">
      <img src="assets/logo.png" alt="{BRAND['lab_name']}" class="logo" onerror="this.style.display='none';document.getElementById('logo-fb').style.display='block'">
      <span id="logo-fb" style="display:none">{logo_svg()}</span>
      <h1>{BRAND['lab_name']}</h1>
      <p class="teacher">{BRAND['teacher']}</p>
      <p class="contact">📞 {BRAND['phone']} &nbsp; 💬 {BRAND['whatsapp']}</p>
    </header>
    <h2 class="lesson-title">{title}</h2>
    <button id="btn-start" class="primary-btn">ابدأ التجربة</button>
  </section>

  <!-- 2+4. منطقة العمل + لوحة التحكم -->
  <section id="workspace" class="screen hidden">
    <div class="lab-table" id="lab-table">
      <canvas id="stage" width="800" height="500"></canvas>
      <aside class="toolbar" id="toolbar">
        <button class="tool" data-tool="flask" title="دورق">🧪</button>
        <button class="tool" data-tool="tube" title="أنبوب اختبار">🧫</button>
        <button class="tool" data-tool="burner" title="موقد">🔥</button>
        <button class="tool" data-tool="balance" title="ميزان">⚖️</button>
      </aside>
    </div>

    <!-- 3. صندوق الشرح المختصر -->
    <div id="brief-box" class="brief hidden">
      <button id="brief-toggle" aria-label="إظهار/إخفاء الشرح">▾</button>
      <p id="brief-text">—</p>
    </div>

    <!-- لوحة التحكم -->
    <div class="control-panel">
      <button id="btn-reset">إعادة التجربة</button>
      <button id="btn-hint">تلميح</button>
      <button id="btn-equation">إظهار المعادلة</button>
      <button id="btn-vars">تغيير المتغيرات</button>
    </div>
  </section>

  <!-- 5. شاشة الإنجاز -->
  <section id="complete-screen" class="screen hidden">
    <h2>🎉 أحسنت!</h2>
    <p>النقاط: <span id="points">0</span></p>
    <div class="nav-buttons">
      <button id="btn-next" class="primary-btn">الدرس التالي</button>
      <button id="btn-list" class="ghost-btn">قائمة الدروس</button>
    </div>
  </section>

  <!-- التذييل الموحّد (يملؤه layout.js) -->
  <div id="site-footer"></div>

  <script>
    // أنيميشن خرافي: يُفعّل المستوى الكامل على سطح المكتب عبر LabFX
    document.addEventListener("DOMContentLoaded", function () {{
      if (window.LabFX && window.LabFX.isEpic && window.LabFX.isEpic()) {{
        var wt = document.getElementById("lab-table");
        if (wt) window.LabFX.ambientGlow(wt);
        window.LabFX.staggerIn(Array.from(document.querySelectorAll(".tool")));
      }}
    }});
  </script>
</body>
</html>'''


def gen_css():
    return f''':root{{
  --c-primary:{BRAND['primary']};
  --c-secondary:{BRAND['secondary']};
  --c-white:{BRAND['white']};
  --bg-dark:{BRAND['bg_dark']};
  --bg-light:{BRAND['bg_light']};
  --font-ar:"Noto Kufi Arabic","Amiri",serif;
  --font-en:"Inter","Roboto",sans-serif;
}}
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:var(--font-ar);background:var(--bg-dark);color:var(--c-white);}}
.screen{{min-height:100vh;display:flex;flex-direction:column;align-items:center;justify-content:center;padding:1rem;gap:1rem}}
.hidden{{display:none!important}}
.brand{{text-align:center}}
.logo{{max-width:140px}}
.logo-fallback{{width:120px;height:120px;display:inline-block}}
.teacher{{color:var(--c-primary);font-size:.95rem}}
.contact{{font-size:.85rem;opacity:.85}}
.primary-btn{{background:var(--c-primary);color:var(--bg-dark);border:none;padding:.8rem 2rem;border-radius:12px;font-weight:700;font-size:1.1rem;cursor:pointer}}
.ghost-btn{{background:transparent;border:1px solid var(--c-primary);color:var(--c-primary);padding:.8rem 2rem;border-radius:12px;cursor:pointer}}
.lesson-title{{font-size:1.6rem;color:var(--c-white)}}
.lab-table{{position:relative;width:100%;max-width:900px;background:linear-gradient(180deg,var(--bg-light),#e6ebf5);border-radius:16px;padding:1rem}}
#stage{{width:100%;height:auto;background:transparent;border-radius:12px;touch-action:none}}
.toolbar{{display:flex;gap:.5rem;flex-wrap:wrap;justify-content:center;margin-top:.5rem}}
.tool{{font-size:1.6rem;background:var(--c-white);border:2px solid var(--c-secondary);border-radius:10px;width:56px;height:56px;cursor:grab}}
.control-panel{{display:flex;gap:.5rem;flex-wrap:wrap;justify-content:center}}
.control-panel button{{background:var(--c-secondary);color:var(--c-white);border:none;padding:.6rem 1rem;border-radius:10px;cursor:pointer;font-family:var(--font-ar)}}
.brief{{position:relative;background:rgba(10,14,39,.85);border:1px solid var(--c-primary);border-radius:10px;padding:.6rem 1rem;max-width:600px}}
.brief p{{font-size:.95rem;line-height:1.4}}
#brief-toggle{{position:absolute;top:-12px;left:8px;background:var(--c-primary);border:none;border-radius:50%;width:26px;height:26px;cursor:pointer;color:var(--bg-dark)}}
.nav-buttons{{display:flex;gap:1rem}}
/* هواتف: أدوات بشريط سفلي + أزرار أكبر */
@media (max-width:600px){{
  #stage{{height:46vh}}
  .tool{{width:64px;height:64px;font-size:1.8rem}}
  .control-panel button{{padding:.8rem 1.1rem;font-size:1rem}}
}}
'''


def gen_experiment_js():
    return '''// experiment.js — منطق التجربة التفاعلية (موجّه بـ design-XX.md)
// ابدأ من هنا: اربط أزرار لوحة التحكم وأدوات شريط الأدوات بحالة التجربة.
(function () {
  "use strict";
  const state = { variables: {}, score: 0, done: false };
  const ELEMENTS = {
    start: document.getElementById("btn-start"),
    workspace: document.getElementById("workspace"),
    complete: document.getElementById("complete-screen"),
    brief: document.getElementById("brief-box"),
    briefText: document.getElementById("brief-text"),
    briefToggle: document.getElementById("brief-toggle"),
    reset: document.getElementById("btn-reset"),
    hint: document.getElementById("btn-hint"),
    equation: document.getElementById("btn-equation"),
    vars: document.getElementById("btn-vars"),
    points: document.getElementById("points"),
  };

  function setBrief(text) {
    ELEMENTS.briefText.textContent = text; // 2-3 سطور كحد أقصى
    ELEMENTS.brief.classList.remove("hidden");
  }
  function showComplete() {
    ELEMENTS.points.textContent = state.score;
    ELEMENTS.workspace.classList.add("hidden");
    ELEMENTS.complete.classList.remove("hidden");
  }

  ELEMENTS.start.addEventListener("click", () => {
    document.getElementById("start-screen").classList.add("hidden");
    ELEMENTS.workspace.classList.remove("hidden");
    setBrief("ابدأ بسحب الأداة إلى منطقة العمل ولاحظ ما يحدث.");
  });
  ELEMENTS.briefToggle.addEventListener("click", () =>
    ELEMENTS.brief.classList.toggle("hidden"));
  ELEMENTS.reset.addEventListener("click", () => location.reload());
  ELEMENTS.hint.addEventListener("click", () =>
    setBrief("جرّب تغيير المتغير الأساسي وراقب الرسم البياني."));
  ELEMENTS.equation.addEventListener("click", () =>
    setBrief("المعادلة: $$H_2 + Cl_2 \\rightarrow 2HCl$$ (استبدل من الدرس)."));
  ELEMENTS.vars.addEventListener("click", () =>
    setBrief("غيّر التركيز ولاحظ سرعة التفاعل."));
  ELEMENTS.complete && document.getElementById("btn-next")
    .addEventListener("click", () => showComplete());

  // TODO: اربط أحداث السحب/الإفلات واللمس من design-XX.md.
  window.__labState = state;
})();
'''


def gen_molecules_js():
    return '''// molecules.js — رسم جزيئي على Canvas 2D (كرات وعصي، قابل للتدوير)
(function () {
  "use strict";
  const canvas = document.getElementById("stage");
  if (!canvas) return;
  const ctx = canvas.getContext("2d");
  let angle = 0;

  // مثال: ذرتان مرتبطتان. استبدل ببيانات الدرس.
  const atoms = [
    { x: -40, y: 0, z: 0, r: 22, color: "#00D4FF" },
    { x: 40, y: 0, z: 0, r: 22, color: "#1A237E" },
  ];
  const bonds = [[0, 1]];

  function project(a) {
    const x = a.x * Math.cos(angle) - a.z * Math.sin(angle);
    const z = a.x * Math.sin(angle) + a.z * Math.cos(angle);
    return { sx: canvas.width / 2 + x, sy: canvas.height / 2 + a.y, depth: z };
  }
  function draw() {
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    for (const [i, j] of bonds) {
      const p = project(atoms[i]), q = project(atoms[j]);
      ctx.strokeStyle = "#FFFFFF"; ctx.lineWidth = 4;
      ctx.beginPath(); ctx.moveTo(p.sx, p.sy); ctx.lineTo(q.sx, q.sy); ctx.stroke();
    }
    for (const a of atoms) {
      const p = project(a);
      ctx.fillStyle = a.color;
      ctx.beginPath(); ctx.arc(p.sx, p.sy, a.r, 0, Math.PI * 2); ctx.fill();
    }
    angle += 0.01;
    requestAnimationFrame(draw);
  }
  draw();
})();
'''


def gen_charts_js():
    return '''// charts.js — رسم بياني متغير عبر Chart.js (خفيف)
(function () {
  "use strict";
  // مثال: أنشئ الرسم عند الحاجة وحدّثه عبر window.updateLabChart(data).
  let chart = null;
  window.updateLabChart = function (labels, values) {
    const el = document.getElementById("labChart");
    if (!el) {
      const c = document.createElement("canvas");
      c.id = "labChart";
      document.querySelector(".lab-table").appendChild(c);
    }
    const ctx = document.getElementById("labChart").getContext("2d");
    if (chart) { chart.data.labels = labels; chart.data.datasets[0].data = values; chart.update(); return; }
    chart = new Chart(ctx, {
      type: "line",
      data: { labels, datasets: [{ label: "القيمة", data: values, borderColor: "#00D4FF", backgroundColor: "rgba(0,212,255,.2)" }] },
      options: { responsive: true, animation: { duration: 300 } },
    });
  };
})();
'''


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--lesson", required=True, help="Lesson number, e.g. 01")
    ap.add_argument("--title", required=True, help="Lesson title (Arabic)")
    ap.add_argument("--design", default="", help="Path to design-XX.md (used for reference only)")
    ap.add_argument("--root", required=True, help="Path to frontend/ repo root")
    ap.add_argument("--docker", action="store_true", help="Emit Docker files (FIRST lesson only)")
    args = ap.parse_args()

    root = pathlib.Path(args.root)
    lesson_dir = root / "lessons" / f"lesson-{args.lesson}"
    (lesson_dir / "css").mkdir(parents=True, exist_ok=True)
    (lesson_dir / "js").mkdir(parents=True, exist_ok=True)
    (lesson_dir / "assets").mkdir(parents=True, exist_ok=True)

    (lesson_dir / "index.html").write_text(gen_index_html(args.title, args.lesson), encoding="utf-8")
    (lesson_dir / "css" / "lab-style.css").write_text(gen_css(), encoding="utf-8")
    (lesson_dir / "js" / "experiment.js").write_text(gen_experiment_js(), encoding="utf-8")
    (lesson_dir / "js" / "molecules.js").write_text(gen_molecules_js(), encoding="utf-8")
    (lesson_dir / "js" / "charts.js").write_text(gen_charts_js(), encoding="utf-8")

    if args.docker:
        docker_root = root.parent / "docker"
        docker_root.mkdir(parents=True, exist_ok=True)
        for f in ("docker-compose.yml", "Dockerfile.frontend", "nginx.conf"):
            shutil.copy(DOCKER_SRC / f, docker_root / f)
        # also place compose at repo root
        shutil.copy(DOCKER_SRC / "docker-compose.yml", root.parent / "docker-compose.yml")
        print("Docker files written (first-lesson only).")

    print(f"Scaffolded: {lesson_dir}")


if __name__ == "__main__":
    main()
