#!/usr/bin/env python3
"""Chem Spectrum Lab - Step 04 integration scaffold.

Builds the integrated site shell around the standalone lesson labs from step 03,
and registers lessons one at a time in Jordanian-book order.

Usage:
    # 1) initialize the shell once:
    python scaffold.py --init --root "<path>/frontend"

    # 2) add ONE lesson at a time (teacher states number/placement):
    python scaffold.py --add-lesson 03 --title "تفاعل الأيونات" --root "<path>/frontend"

The teacher's chosen lesson number is honored; the card is inserted into
shared/lessons-data.js in numeric order. Docker files are copied only if absent
(they belong to step 03's first lesson).
"""
import argparse, json, os, pathlib, re, shutil, sys

SKILL_DIR = pathlib.Path(__file__).resolve().parent.parent
DOCKER_SRC = SKILL_DIR / "references" / "docker"

TEACHER = "م. معتصم جادالله (مهندس) — مدرس كيمياء"
PHONE = "0788521514"
WHATS = "+962 78 852 1514"
LAB = "مختبر الطيف للكيمياء"


def header_html():
    return f'''<header id="site-header">
  <a class="brand" href="index.html">
    <img src="assets/logo.png" alt="{LAB}" class="logo"
         onerror="this.style.display='none';document.getElementById('hfb').style.display='inline-block'">
    <span id="hfb" class="logo-fallback-text" style="display:none">🔬 {LAB}</span>
  </a>
  <nav>
    <a href="index.html">الرئيسية</a>
    <a href="lessons.html">الدروس</a>
    <a href="about.html">عن المختبر</a>
    <a href="contact.html">التواصل</a>
  </nav>
  <div class="header-right">
    <button id="theme-toggle" aria-label="تبديل الوضع">🌙</button>
    <span id="student-name"></span>
  </div>
</header>'''


def footer_html():
    return f'''<footer id="site-footer">
  <p>© 2026 {LAB} | {TEACHER}</p>
  <p>📞 {PHONE} &nbsp; 💬 {WHATS}</p>
</footer>'''


def layout_js():
    return '''// layout.js — حقن الرأس/التذييل + شاشة الترحيب + الثيم + الاسم
(function () {
  "use strict";
  const HEADER = `''' + header_html().replace("`", "\\`") + '''`;
  const FOOTER = `''' + footer_html().replace("`", "\\`") + '''`;
  document.addEventListener("DOMContentLoaded", () => {
    inject("site-header", HEADER);
    inject("site-footer", FOOTER);
    ChemLabStorage.applyTheme();
    bindThemeToggle();
    maybeWelcome();
    showName();
  });
  function inject(id, html) {
    const el = document.getElementById(id);
    if (el && !el.childElementCount) el.outerHTML = html;
  }
  function bindThemeToggle() {
    const t = document.getElementById("theme-toggle");
    t && t.addEventListener("click", () => {
      const next = ChemLabStorage.getTheme() === "dark" ? "light" : "dark";
      ChemLabStorage.setTheme(next);
      ChemLabStorage.applyTheme();
    });
  }
  function showName() {
    const n = document.getElementById("student-name");
    const name = ChemLabStorage.getUserName();
    if (n && name) n.textContent = "👤 " + name;
  }
  function maybeWelcome() {
    if (ChemLabStorage.getUserName() !== null) return;
    const box = document.createElement("div");
    box.id = "welcome";
    box.innerHTML = `<div class="welcome-card">
      <h2>مرحباً بك في ${LAB}!</h2>
      <p>ما اسمك؟</p>
      <input id="w-name" type="text" placeholder="اسمك">
      <button id="w-go">ابدأ الرحلة</button>
      <button id="w-skip" class="ghost">تخطي</button>
    </div>`;
    document.body.appendChild(box);
    box.querySelector("#w-go").onclick = () => {
      const v = box.querySelector("#w-name").value.trim();
      if (v) ChemLabStorage.setUserName(v);
      box.remove(); showName();
    };
    box.querySelector("#w-skip").onclick = () => { ChemLabStorage.setUserName(""); box.remove(); };
  }
})();
'''


def storage_js():
    return '''// storage.js — ChemLabStorage (LocalStorage الآن، API لاحقاً)
const ChemLabStorage = {
  KEY: "chemlab:",
  _get(k){ return localStorage.getItem(this.KEY + k); },
  _set(k,v){ localStorage.setItem(this.KEY + k, v); },
  getUserName(){ const v = this._get("name"); return v === null ? null : v; },
  setUserName(name){ this._set("name", name); },
  getProgress(){ try { return JSON.parse(this._get("progress") || "{}"); } catch(e){ return {}; } },
  markLessonComplete(id){ const p = this.getProgress(); p[id] = true; this._set("progress", JSON.stringify(p)); },
  getTheme(){ return this._get("theme") || "dark"; },
  setTheme(t){ this._set("theme", t); document.documentElement.setAttribute("data-theme", t); },
  applyTheme(){ document.documentElement.setAttribute("data-theme", this.getTheme()); },
  getLastLesson(){ return this._get("last"); },
  setLastLesson(id){ this._set("last", id); },
  // لاحقاً: استبدل الدوال الداخلية بنداءات API دون تغيير العقد.
};
'''


def nav_js():
    return '''// nav.js — سابق/تالي + شريط تقدم (داخل المختبر)
(function () {
  "use strict";
  const LESSONS = window.LESSONS || [];
  const here = location.pathname.match(/lesson-(\\d+)/);
  if (!here) return;
  const idx = LESSONS.findIndex(l => l.id === "lesson-" + here[1]);
  const prev = LESSONS[idx - 1], next = LESSONS[idx + 1];
  ChemLabStorage.markLessonComplete(LESSONS[idx].id);
  const bar = document.createElement("div");
  bar.className = "lesson-nav";
  bar.innerHTML = `<a href="lessons.html" class="ghost-btn">قائمة الدروس</a>
    ${prev ? `<a href="${prev.id}/index.html" class="primary-btn">← ${prev.title}</a>` : ""}
    ${next ? `<a href="${next.id}/index.html" class="primary-btn">${next.title} →</a>` : ""}
    <div class="progress"><div class="fill" style="width:${Math.round((idx+1)/LESSONS.length*100)}%"></div></div>`;
  document.querySelector(".lab-table")?.appendChild(bar);
})();
'''


def lessons_data_js(lessons):
    arr = json.dumps([{"id": l["id"], "title": l["title"], "thumb": l.get("thumb", "")} for l in lessons], ensure_ascii=False, indent=2)
    return f"// lessons-data.js — يولّده السكافولد. الدروس بترتيب الكتاب الأردني.\nwindow.LESSONS = {arr};\n"


def lessons_html(lessons):
    cards = "\n".join(
        f'''      <a class="lesson-card" href="lessons/{l['id']}/index.html">
        <div class="thumb">{('<img src="'+l['thumb']+'" alt="'+l['title']+'">' if l.get('thumb') else '🧪')}</div>
        <h3>{l['title']}</h3>
        <span class="enter">ادخل المختبر ←</span>
        <span class="done-badge" hidden>✓ مكتمل</span>
      </a>''' for l in lessons)
    return f'''<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>قائمة الدروس — {LAB}</title>
  <link href="https://fonts.googleapis.com/css2?family=Noto+Kufi+Arabic:wght@400;700&display=swap" rel="stylesheet">
  <link rel="stylesheet" href="css/site.css">
  <link rel="stylesheet" href="shared/theme.css">
</head>
<body data-theme="dark">
  <div id="site-header"></div>
  <main class="lessons-page">
    <h1>الدروس</h1>
    <div class="lesson-grid">
{cards}
    </div>
  </main>
  <div id="site-footer"></div>
  <script src="shared/storage.js"></script>
  <script src="shared/lessons-data.js"></script>
  <script src="shared/layout.js"></script>
  <script>
    // إظهار علامة "مكتمل" للدروس المنجزة
    document.querySelectorAll('.lesson-card').forEach((c,i)=>{{
      if (ChemLabStorage.getProgress()[window.LESSONS[i].id]) c.querySelector('.done-badge').hidden=false;
    }});
  </script>
</body>
</html>'''


def simple_page(name, title, body):
    return f'''<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{title} — {LAB}</title>
  <link href="https://fonts.googleapis.com/css2?family=Noto+Kufi+Arabic:wght@400;700&display=swap" rel="stylesheet">
  <link rel="stylesheet" href="css/site.css">
  <link rel="stylesheet" href="shared/theme.css">
</head>
<body data-theme="dark">
  <div id="site-header"></div>
  <main class="page">
{body}
  </main>
  <div id="site-footer"></div>
  <script src="shared/storage.js"></script>
  <script src="shared/lessons-data.js"></script>
  <script src="shared/layout.js"></script>
  <script src="shared/device.js"></script>
  <script src="shared/fx.js"></script>
</body>
</html>'''


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--init", action="store_true", help="Initialize the site shell (once)")
    ap.add_argument("--add-lesson", metavar="N", help="Lesson number, e.g. 03 (ONE at a time)")
    ap.add_argument("--title", help="Lesson title (Arabic)")
    ap.add_argument("--thumb", default="", help="Optional thumbnail image path")
    ap.add_argument("--root", required=True, help="Path to frontend/ repo root")
    args = ap.parse_args()

    root = pathlib.Path(args.root)
    shared = root / "shared"
    css = root / "css"
    assets = root / "assets"
    data_js = shared / "lessons-data.js"

    if args.init:
        for d in (shared, css, assets):
            d.mkdir(parents=True, exist_ok=True)
        (root / "index.html").write_text(simple_page("home", "الرئيسية",
            f'''    <section class="hero">
      <h1>{LAB}</h1>
      <p class="tagline">الفهم قبل الحفظ</p>
      <a href="lessons.html" class="primary-btn">استكشف الدروس</a>
      <p class="teacher">{TEACHER}</p>
      <p class="contact">📞 {PHONE} &nbsp; 💬 {WHATS}</p>
    </section>
    <section class="cards">
      <div class="info-card"><h3>تجارب تفاعلية</h3><p>تعلم بالتجربة لا بالحفظ.</p></div>
      <div class="info-card"><h3>الفهم أولاً</h3><p>كل تفاعل يجيب "لماذا؟".</p></div>
      <div class="info-card"><h3>يعمل على كل الأجهزة</h3><p>هاتفاً كان أو حاسوباً.</p></div>
    </section>'''), encoding="utf-8")
        (root / "about.html").write_text(simple_page("about", "عن المختبر",
            f'''    <h1>عن المختبر</h1>
    <p>{LAB} مشروع يهدف إلى تعليم الكيمياء بالتجربة التفاعلية.</p>
    <h2>فلسفة "الفهم قبل الحفظ"</h2>
    <p>نعلمك لماذا يحدث التفاعل قبل أن تحفظ ماذا يحدث.</p>
    <h2>نبذة عن المدرس</h2>
    <p>{TEACHER}</p>
    <h2>الرؤية والرسالة</h2>
    <p>مختبر كيميائي تفاعلي لكل طالب توجيهي.</p>'''), encoding="utf-8")
        (root / "contact.html").write_text(simple_page("contact", "التواصل",
            f'''    <h1>التواصل</h1>
    <p>📞 {PHONE}</p>
    <p>💬 {WHATS}</p>
    <p>{TEACHER}</p>'''), encoding="utf-8")
        (root / "lessons.html").write_text(lessons_html([]), encoding="utf-8")
        (css / "site.css").write_text(SITE_CSS, encoding="utf-8")
        (shared / "theme.css").write_text(THEME_CSS, encoding="utf-8")
        (shared / "storage.js").write_text(storage_js(), encoding="utf-8")
        (shared / "layout.js").write_text(layout_js(), encoding="utf-8")
        (shared / "nav.js").write_text(nav_js(), encoding="utf-8")
        (shared / "lessons-data.js").write_text(lessons_data_js([]), encoding="utf-8")
        # Docker: copy only if absent (belongs to step 03 first lesson)
        docker_root = root.parent / "docker"
        if not docker_root.exists():
            docker_root.mkdir(parents=True, exist_ok=True)
            for f in ("docker-compose.yml", "Dockerfile.frontend", "nginx.conf"):
                shutil.copy(DOCKER_SRC / f, docker_root / f)
            shutil.copy(DOCKER_SRC / "docker-compose.yml", root.parent / "docker-compose.yml")
        print("Site shell initialized at", root)

    if args.add_lesson:
        if not args.title:
            sys.exit("--title is required when adding a lesson")
        lessons = []
        if data_js.exists():
            m = re.search(r"window\.LESSONS = (.*);", data_js.read_text(encoding="utf-8"), re.S)
            if m:
                lessons = json.loads(m.group(1))
        # honor teacher-stated number; insert in numeric order
        lid = f"lesson-{args.add_lesson.zfill(2)}"
        lessons.append({"id": lid, "title": args.title, "thumb": args.thumb})
        lessons.sort(key=lambda l: l["id"])
        data_js.write_text(lessons_data_js(lessons), encoding="utf-8")
        (root / "lessons.html").write_text(lessons_html(lessons), encoding="utf-8")
        print(f"Added {lid}: {args.title} (total {len(lessons)} lessons, in book order)")
        print("NOTE: the lesson lab folder (from step 03) must exist at", root / "lessons" / lid)

    if not args.init and not args.add_lesson:
        sys.exit("Use --init or --add-lesson")


SITE_CSS = '''* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: "Noto Kufi Arabic", serif; min-height: 100vh; display: flex; flex-direction: column; }
#site-header, #site-footer { padding: 1rem 1.5rem; }
#site-footer { margin-top: auto; text-align: center; opacity: .85; font-size: .85rem; }
.brand { display: flex; align-items: center; gap: .5rem; font-weight: 700; text-decoration: none; }
.logo { max-width: 120px; }
#site-header { display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: .5rem; border-bottom: 1px solid var(--c-primary); }
#site-header nav { display: flex; gap: 1rem; }
#site-header nav a { color: inherit; text-decoration: none; }
.header-right { display: flex; align-items: center; gap: .75rem; }
#theme-toggle { background: none; border: 1px solid var(--c-primary); border-radius: 50%; width: 36px; height: 36px; cursor: pointer; color: inherit; }
.primary-btn { background: var(--c-primary); color: var(--bg-dark); border: none; padding: .7rem 1.6rem; border-radius: 12px; font-weight: 700; text-decoration: none; display: inline-block; }
.ghost-btn { background: transparent; border: 1px solid var(--c-primary); color: var(--c-primary); padding: .7rem 1.6rem; border-radius: 12px; text-decoration: none; }
.hero { text-align: center; padding: 4rem 1rem; }
.hero .tagline { color: var(--c-primary); font-size: 1.4rem; margin: 1rem 0; }
.cards { display: flex; gap: 1rem; justify-content: center; flex-wrap: wrap; padding: 2rem; }
.info-card { background: rgba(0,212,255,.08); border: 1px solid var(--c-primary); border-radius: 14px; padding: 1.2rem; max-width: 240px; }
.page { max-width: 800px; margin: 0 auto; padding: 2rem 1rem; line-height: 1.9; }
.lessons-page { padding: 2rem 1rem; text-align: center; }
.lesson-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: 1.2rem; max-width: 1000px; margin: 2rem auto; }
.lesson-card { position: relative; background: rgba(0,212,255,.06); border: 1px solid var(--c-primary); border-radius: 14px; padding: 1rem; text-decoration: none; color: inherit; text-align: center; }
.lesson-card .thumb { font-size: 3rem; margin-bottom: .5rem; }
.lesson-card .enter { color: var(--c-primary); font-weight: 700; }
.lesson-card .done-badge { position: absolute; top: 8px; left: 8px; background: var(--c-primary); color: var(--bg-dark); border-radius: 8px; padding: 2px 8px; font-size: .8rem; }
.welcome-card { position: fixed; inset: 0; margin: auto; width: min(90vw, 360px); height: fit-content; background: var(--bg-dark); border: 1px solid var(--c-primary); border-radius: 16px; padding: 2rem; text-align: center; z-index: 50; }
.welcome-card input { width: 100%; padding: .7rem; margin: .5rem 0; border-radius: 10px; border: 1px solid var(--c-primary); }
.welcome-card button { margin: .3rem; padding: .6rem 1.2rem; border-radius: 10px; border: none; background: var(--c-primary); color: var(--bg-dark); cursor: pointer; font-weight: 700; }
.welcome-card .ghost { background: transparent; border: 1px solid var(--c-primary); color: var(--c-primary); }
.lesson-nav { display: flex; gap: .5rem; flex-wrap: wrap; align-items: center; margin-top: 1rem; }
.lesson-nav .progress { flex: 1; min-width: 120px; height: 8px; background: rgba(255,255,255,.15); border-radius: 6px; overflow: hidden; }
.lesson-nav .progress .fill { height: 100%; background: var(--c-primary); }
@media (max-width: 600px){ #site-header nav { font-size: .9rem; gap: .5rem; } .primary-btn, .ghost-btn { padding: .8rem 1.2rem; } }
'''

THEME_CSS = ''':root { --c-primary:#00D4FF; --c-secondary:#1A237E; --c-white:#FFFFFF; --bg-dark:#0A0E27; --bg-light:#F5F7FA; }
[data-theme="dark"] { background: var(--bg-dark); color: var(--c-white); }
[data-theme="light"] { background: var(--bg-light); color: var(--bg-dark);
  --bg-dark: #1A237E; } /* keep primary readable on light */
[data-theme="dark"] #site-header, [data-theme="dark"] #site-footer { box-shadow: 0 0 12px rgba(0,212,255,.25); }
[data-theme="light"] .info-card, [data-theme="light"] .lesson-card { background: rgba(26,35,126,.06); }
'''


if __name__ == "__main__":
    main()
