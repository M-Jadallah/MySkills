#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
مصنع خطط الحفظ — quran-plan-factory
استخراج خطة حفظ مخصصة من اللقطة المجمّدة للخطة المنهجية (assets/master_plan.csv).

القاعدة الصارمة: الخطة الأم مصدر للقراءة فقط، ولا تُعدَّل أبداً. المهارة تعمل على اللقطة.

الأوامر:
  lookup [--csv PATH]
      عرض فهرس السور (أول/آخر يوم، الأجزاء، الصفحات) وفهرس الأجزاء.

  build --spec SPEC.json --out OUT.xlsx [--csv PATH]
      بناء خطة مخصصة من مواصفة JSON:
      {"segments": [
        {"type": "surah", "name": "النمل"},
        {"type": "surah_range", "from": "مريم", "to": "الأنبياء"},
        {"type": "juz", "number": 9},
        {"type": "juz_range", "from": 27, "to": 28}
      ]}

دلالات الاستخراج (مطابقة لبنية الخطة الأم):
  - السورة المفردة: امتدادها المتصل في الخطة (أول ظهور في الأعمدة C/D/E إلى آخر
    ظهور لها) + شهاداتها الخاصة (سورة X تراكمي / تسميع سورة X)، وشهادات الأجزاء
    المضمّنة داخل الامتداد تبقى كما في الأم. أما شهادة الجزء الواقعة عند حدود
    السورة (مثل «جزء 19 تراكمي» الموسومة بآخر سورة في الجزء) فلا تُجرّ مع طلب
    السورة وحدها.
  - مدى السور: كل السور بين الطرفين بترتيب المصحف كما في الخطة، وتُدرج كل صفوف
    النطاق كما هي — ومنها شهادات الأجزاء الواقعة داخله.
  - الجزء (مفرد أو مدى): كل الصفوف التي يحملها عمود «الجزء» (B) حرفياً.
  - الدمج: اتحاد الأيام من كل المقاطع بلا تكرار، مرتبة حسب الخطة الأم،
    وترقيم جديد متصل 1..N.
"""

import argparse
import csv
import json
import re
import sys
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent
DEFAULT_CSV = SKILL_DIR / "assets" / "master_plan.csv"

# أيام «دوري» أُضيفت بالتصحيح رقم 5 في الخطة الأم (مظللة بالأصفر) — نحافظ على تظليلها
SPECIAL_YELLOW_DAYS = {101, 150, 216}
BAND_FILL = "F3F7F3"    # التظليل المتناوب في الخطة الأم
YELLOW_FILL = "FFF2CC"  # تظليل الأيام المضافة

HEADERS = [
    "sort_order", "الجزء", "السورة الأولى", "السورة الثانية", "السورة الثالثة",
    "خطة التسميع", "النقاط", "الوزن", "منفرد", "أخذ الشهادة",
    "اسم السورة", "اسم الجزء", "رقم الثلاث أجزاء",
]
# صيغة الملف الناتج: بلا أعمدة الجزء/السور، وعمود id فارغ في أول الملف
OUTPUT_HEADERS = [
    "id", "sort_order", "خطة التسميع", "النقاط", "الوزن", "منفرد",
    "أخذ الشهادة", "اسم السورة", "اسم الجزء", "رقم الثلاث أجزاء",
]
OUTPUT_COL_WIDTHS = {"A": 10.0, "B": 13.6, "C": 40.0, "D": 8.1, "E": 7.0,
                     "F": 8.6, "G": 14.0, "H": 12.9, "I": 18.7, "J": 24.7}

DIACRITICS = re.compile(r"[\u064B-\u0652\u0670\u0640]")
AR_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")

TRIPLE_RE = re.compile(r"^\(\s*(\d+)\s*\+\s*(\d+)\s*\+\s*(\d+)\s*\)$")
BLOCK_RE = re.compile(r"^من\s*\[\s*(\d+)\s*[-–]\s*(\d+)\s*\]$")
TASMEE_PAGE_RE = re.compile(r"^تسميع\s+(\d+)$")
RANGE_REVIEW_RE = re.compile(r"^تسميع\s*\(\s*(\d+)\s*[-–]\s*(\d+)\s*\)$")
SURAH_CERT_RE = re.compile(r"^(?:سورة\s+|تسميع\s+سورة\s+)(.+?)(?:\s+تراكمي)?$")
JUZ_CERT_NAMES = ("تسميع الجزء", "تسميع جزء ونصف", "تسميع الجزئين")


def norm(s):
    """تطبيع عربي للمطابقة: إزالة التشكيل، توحيد الهمزات، الأرقام المشرقية."""
    if s is None:
        return ""
    s = str(s).translate(AR_DIGITS)
    s = DIACRITICS.sub("", s)
    for a, b in (("أ", "ا"), ("إ", "ا"), ("آ", "ا"), ("ٱ", "ا"),
                 ("ى", "ي"), ("ة", "ه"), ("ؤ", "و"), ("ئ", "ي")):
        s = s.replace(a, b)
    return re.sub(r"\s+", " ", s).strip()


def load_rows(csv_path):
    """تحميل اللقطة: قائمة صفوف بقيم أعمدة الخطة الأم."""
    rows = []
    with open(csv_path, newline="", encoding="utf-8-sig") as fh:
        reader = csv.reader(fh)
        header = next(reader)
        if header[:len(HEADERS)] != HEADERS:
            raise SystemExit("خطأ: ملف اللقطة غير مطابق للبنية المتوقعة.")
        for rec in reader:
            if not rec or all(not x.strip() for x in rec):
                continue
            rows.append({
                "sort": int(rec[0]),
                "juz": int(rec[1]),
                "c": rec[2].strip(),
                "d": rec[3].strip(),
                "e": rec[4].strip(),
                "f": rec[5].strip(),
                "points": int(rec[6]),
                "weight": int(rec[7]),
                "single": int(rec[8]) if rec[8].strip() else None,
            })
    rows.sort(key=lambda r: r["sort"])
    return rows


def row_kind(f):
    """تصنيف بند خطة التسميع: حفظ صفحة / دوري / مراجعة / شهادة."""
    s = f.strip()
    if re.fullmatch(r"\d+", s) or TASMEE_PAGE_RE.match(s):
        return "حفظ صفحة"
    if s == "دوري":
        return "دوري"
    if BLOCK_RE.match(s) or RANGE_REVIEW_RE.match(s):
        return "مراجعة"
    return "شهادة"


def row_page(f):
    """رقم الصفحة إن كان البند حفظ صفحة، وإلا None."""
    s = f.strip()
    if re.fullmatch(r"\d+", s):
        return int(s)
    m = TASMEE_PAGE_RE.match(s)
    return int(m.group(1)) if m else None


def cert_surah(f):
    """اسم السورة التي تشهدها الشهادة، أو None إن كانت شهادة جزء/ثلاثية."""
    s = f.strip()
    if s == "دوري" or row_kind(s) != "شهادة":
        return None
    if s.startswith("تسميع جزء") or s in JUZ_CERT_NAMES or TRIPLE_RE.match(s):
        return None
    if "عمّ +" in s or "عم +" in s:  # تسميع جزء عمّ + جزء تبارك + قد سمع
        return None
    m = SURAH_CERT_RE.match(s)
    return norm(m.group(1)) if m else None


def is_juz_cert(f):
    """هل البند شهادة جزء أو ثلاثية أجزاء؟"""
    s = f.strip()
    if row_kind(s) != "شهادة":
        return False
    if cert_surah(s):
        return False
    return True


def is_extended_cert(f):
    """شهادة ممتدة على أكثر من جزء (للتنبيه عليها في الملخص)."""
    s = f.strip()
    return bool(TRIPLE_RE.match(s) or "عمّ +" in s or "عم +" in s
                or "جزء ونصف" in s or "الجزئين" in s)


def build_indices(rows):
    """فهارس السور (بترتيب الظهور في الخطة = ترتيب المصحف) والأجزاء."""
    surah_first, surah_last = {}, {}
    for r in rows:
        for name in (r["c"], r["d"], r["e"]):
            if not name:
                continue
            k = norm(name)
            surah_first.setdefault(k, r["sort"])
            if r["sort"] > surah_last.get(k, 0):
                surah_last[k] = r["sort"]
    surah_order = list(dict.fromkeys(
        norm(n) for r in rows for n in (r["c"], r["d"], r["e"]) if n
    ))
    display = {}
    for r in rows:
        for name in (r["c"], r["d"], r["e"]):
            if name:
                display.setdefault(norm(name), name)
    juz_rows = {}
    for r in rows:
        juz_rows.setdefault(r["juz"], []).append(r["sort"])
    return surah_first, surah_last, surah_order, display, juz_rows


def surah_sorts(rows, key, surah_first, surah_last):
    """أيام سورة مفردة: امتدادها غير الشهادي + شهاداتها + شهادات الأجزاء المضمّنة داخله."""
    nc = [r["sort"] for r in rows
          if key in (norm(r["c"]), norm(r["d"]), norm(r["e"]))
          and surah_first[key] <= r["sort"] <= surah_last[key]
          and not is_juz_cert(r["f"])]
    lo, hi = min(nc), max(nc)
    sorts = {r["sort"] for r in rows if lo <= r["sort"] <= hi}
    for r in rows:
        if cert_surah(r["f"]) == key:
            sorts.add(r["sort"])
    return sorted(sorts), lo, hi


def list_runs(sorted_ints):
    """مجموعات متصلة من أعداد مرتبة: [1,2,3,7,8] -> [(1,3),(7,8)]"""
    if not sorted_ints:
        return []
    runs, start, prev = [], sorted_ints[0], sorted_ints[0]
    for v in sorted_ints[1:]:
        if v == prev + 1:
            prev = v
        else:
            runs.append((start, prev))
            start = prev = v
    runs.append((start, prev))
    return runs


def runs_txt(runs):
    return " و".join(f"{a}–{b}" if a != b else str(a) for a, b in runs)


def clean_surah_name(s):
    """تجريد بادئات شائعة قبل التطبيع (سورة/جزء عند طلب سورة)."""
    s = str(s or "").strip()
    s = re.sub(r"^سورة\s+", "", s)
    return s.strip()


def resolve_segments(spec, rows, indices):
    """تحويل مواصفة المقاطع إلى قائمة مقاطع محسومة: وصف + أيام الخطة الأم."""
    surah_first, surah_last, surah_order, display, juz_rows = indices
    segments = spec.get("segments")
    if not segments:
        raise SystemExit("خطأ: المواصفة لا تحتوي على أي مقاطع (segments).")

    def suggest(query_key):
        cands = [display[k] for k in surah_order
                 if query_key in k or k[:4] == query_key[:4]]
        return "، ".join(cands[:6]) if cands else "، ".join(display[k] for k in surah_order[:10])

    resolved = []
    for i, seg in enumerate(segments, 1):
        stype = str(seg.get("type", "")).strip()
        if stype == "surah":
            key = norm(clean_surah_name(seg.get("name", "")))
            if key not in surah_first:
                raise SystemExit(f"خطأ: المقطع {i}: السورة «{seg.get('name')}» غير معروفة. "
                                 f"أسماء قريبة: {suggest(key)}")
            sorts, lo, hi = surah_sorts(rows, key, surah_first, surah_last)
            resolved.append({
                "label": f"سورة {display[key]}",
                "desc": f"سورة {display[key]} — الأيام {runs_txt(list_runs(sorts))} من الخطة الأم",
                "sorts": sorts,
            })
        elif stype == "surah_range":
            k1, k2 = norm(clean_surah_name(seg.get("from", ""))), norm(clean_surah_name(seg.get("to", "")))
            if k1 not in surah_first or k2 not in surah_first:
                bad = seg.get("from") if k1 not in surah_first else seg.get("to")
                raise SystemExit(f"خطأ: المقطع {i}: السورة «{bad}» غير معروفة. "
                                 f"أسماء قريبة: {suggest(norm(bad))}")
            i1, i2 = surah_order.index(k1), surah_order.index(k2)
            if i1 > i2:
                k1, k2, i1, i2 = k2, k1, i2, i1
            members = surah_order[i1:i2 + 1]
            lo = min(surah_first[k] for k in members)
            hi = max(surah_last[k] for k in members)
            sorts = {r["sort"] for r in rows if lo <= r["sort"] <= hi}
            for k in members:  # شهادات السور الأعضاء حتى لو وقعت بعد آخر صف غير شهادي
                for r in rows:
                    if cert_surah(r["f"]) == k:
                        sorts.add(r["sort"])
            member_names = "، ".join(display[k] for k in members)
            resolved.append({
                "label": f"من سورة {display[k1]} إلى سورة {display[k2]}",
                "desc": (f"مدى السور: {display[k1]} → {display[k2]} (يشمل: {member_names}) "
                         f"— الأيام {runs_txt(list_runs(sorted(sorts)))} من الخطة الأم"),
                "sorts": sorted(sorts),
            })
        elif stype == "juz":
            try:
                j = int(seg.get("number"))
            except (TypeError, ValueError):
                raise SystemExit(f"خطأ: المقطع {i}: رقم الجزء غير صحيح: {seg.get('number')!r}")
            if j not in juz_rows:
                raise SystemExit(f"خطأ: المقطع {i}: الجزء {j} غير موجود في الخطة "
                                 f"(الأجزاء المتاحة: {sorted(juz_rows)}).")
            day_list = juz_rows[j]
            resolved.append({
                "label": f"الجزء {j}",
                "desc": f"الجزء {j} — الأيام {runs_txt(list_runs(day_list))} من الخطة الأم",
                "sorts": list(day_list),
            })
        elif stype == "juz_range":
            try:
                j1, j2 = int(seg.get("from")), int(seg.get("to"))
            except (TypeError, ValueError):
                raise SystemExit(f"خطأ: المقطع {i}: أرقام مدى الأجزاء غير صحيحة.")
            if j1 not in juz_rows or j2 not in juz_rows:
                raise SystemExit(f"خطأ: المقطع {i}: أحد الجزأين غير موجود في الخطة "
                                 f"(الأجزاء المتاحة: {sorted(juz_rows)}).")
            if j1 > j2:
                j1, j2 = j2, j1
            wanted = [j for j in sorted(juz_rows) if j1 <= j <= j2]
            sorts = sorted(s for j in wanted for s in juz_rows[j])
            resolved.append({
                "label": f"الجزء {j1}" if j1 == j2 else f"الجزء {j1} إلى الجزء {j2}",
                "desc": (f"مدى الأجزاء {j1}–{j2} (يشمل: {', '.join(map(str, wanted))}) "
                         f"— الأيام {runs_txt(list_runs(sorts))} من الخطة الأم"),
                "sorts": sorts,
            })
        else:
            raise SystemExit(f"خطأ: المقطع {i}: نوع غير معروف «{stype}». "
                             f"الأنواع: surah, surah_range, juz, juz_range.")
    return resolved


def select_rows(resolved, rows):
    """اتحاد الأيام من كل المقاطع بلا تكرار، بترتيب الخطة الأم."""
    chosen = set()
    for seg in resolved:
        chosen.update(seg["sorts"])
    return [r for r in rows if r["sort"] in chosen]


def build_output(selected, resolved, out_path):
    import openpyxl
    from openpyxl.styles import Font, PatternFill

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "الخطة المخصصة"
    ws.sheet_view.rightToLeft = True
    ws.freeze_panes = "A2"

    band = PatternFill("solid", fgColor=BAND_FILL)
    yellow = PatternFill("solid", fgColor=YELLOW_FILL)

    ws.append(OUTPUT_HEADERS)
    for cell in ws[1]:
        cell.font = Font(bold=True)

    for new_no, r in enumerate(selected, 1):
        ws.append([
            None, new_no, r["f"], r["points"], r["weight"], r["single"],
            None, None, None, None,
        ])
        fill = yellow if r["sort"] in SPECIAL_YELLOW_DAYS else (
            band if new_no % 2 == 0 else None)
        if fill:
            for col in range(1, 11):
                ws.cell(row=new_no + 1, column=col).fill = fill

    for col, width in OUTPUT_COL_WIDTHS.items():
        ws.column_dimensions[col].width = width

    # ===== ورقة الملخص =====
    ss = wb.create_sheet("الملخص")
    ss.sheet_view.rightToLeft = True
    title_font = Font(bold=True, size=14)
    head_font = Font(bold=True, size=11)

    row = 1
    ss.cell(row=row, column=1, value="ملخص الخطة المخصصة").font = title_font
    row += 2
    ss.cell(row=row, column=1,
            value="المصدر: اللقطة المجمّدة للخطة المنهجية (master_plan.csv) — قراءة فقط").font = head_font
    row += 1
    ss.cell(row=row, column=1, value="مقاطع الطلب كما حُلّت من الخطة الأم:").font = head_font
    for seg in resolved:
        row += 1
        ss.cell(row=row, column=1, value=f"• {seg['desc']}")

    row += 2
    kinds = {}
    cert_rows = []
    for r in selected:
        k = row_kind(r["f"])
        kinds[k] = kinds.get(k, 0) + 1
        if k == "شهادة":
            cert_rows.append(r)

    pages = sorted({p for r in selected if (p := row_page(r["f"])) is not None})
    raw_points = sum(r["points"] for r in selected)
    weighted_points = sum(r["points"] * r["weight"] for r in selected)

    stats = [
        ("عدد الأيام", len(selected)),
        ("الصفحات المشمولة", f"{len(pages)} صفحة: {runs_txt(list_runs(pages))}" if pages else "لا يوجد حفظ صفحات في هذا المدى"),
        ("أيام حفظ الصفحات", kinds.get("حفظ صفحة", 0)),
        ("أيام الدوري", kinds.get("دوري", 0)),
        ("أيام المراجعات", kinds.get("مراجعة", 0)),
        ("أيام الشهادات", kinds.get("شهادة", 0)),
        ("مجموع النقاط الخام", raw_points),
        ("مجموع النقاط الموزونة", weighted_points),
    ]
    for label, value in stats:
        ss.cell(row=row, column=1, value=label).font = head_font
        ss.cell(row=row, column=2, value=value)
        row += 1

    if cert_rows:
        row += 1
        ss.cell(row=row, column=1, value="الشهادات المشمولة (بترتيب الخطة الأم):").font = head_font
        row += 1
        for h_i, h in enumerate(("اليوم", "البند", "النقاط", "الوزن"), 1):
            ss.cell(row=row, column=h_i, value=h).font = head_font
        for r in cert_rows:
            row += 1
            ss.cell(row=row, column=1, value=r["sort"])
            ss.cell(row=row, column=2, value=r["f"])
            ss.cell(row=row, column=3, value=r["points"])
            ss.cell(row=row, column=4, value=r["weight"])

    extended = [r for r in cert_rows if is_extended_cert(r["f"])]
    if extended:
        row += 2
        ss.cell(row=row, column=1,
                value="ملاحظة: شهادات ممتدة أُدرجت كما في الخطة الأم لوقوعها ضمن نطاق الطلب:").font = head_font
        for r in extended:
            row += 1
            ss.cell(row=row, column=1, value=f"• اليوم {r['sort']}: {r['f']}")

    ss.column_dimensions["A"].width = 60
    ss.column_dimensions["B"].width = 45
    ss.column_dimensions["C"].width = 10
    ss.column_dimensions["D"].width = 8

    wb.properties.creator = "Z.ai"
    out_path = Path(out_path)
    if out_path.suffix.lower() != ".xlsx":
        out_path = out_path.with_suffix(".xlsx")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(out_path)
    return out_path


def self_check(selected):
    """تحقق ذاتي قبل التسليم — يرفع خطأ إن اختل أي شرط."""
    sorts = [r["sort"] for r in selected]
    if not sorts:
        raise SystemExit("فشل التحقق: الاختيار فارغ!")
    if len(sorts) != len(set(sorts)):
        raise SystemExit("فشل التحقق: أيام مكررة في الاختيار!")
    if sorts != sorted(sorts):
        raise SystemExit("فشل التحقق: الترتيب غير مطابق للخطة الأم!")
    bad_pages = [p for r in selected
                 if (p := row_page(r["f"])) is not None and not 1 <= p <= 604]
    if bad_pages:
        raise SystemExit(f"فشل التحقق: صفحات خارج مدى المصحف (1-604): {bad_pages}")
    covered = {row_page(r["f"]) for r in selected
               if row_kind(r["f"]) == "حفظ صفحة"}
    covered.discard(None)
    missing = []
    for a, b in list_runs(sorted(covered)):
        missing.extend(p for p in range(a, b + 1) if p not in covered)
    if missing:
        raise SystemExit(f"فشل التحقق: فجوات داخل نطاقات الصفحات المتصلة: {missing[:10]}")


def print_summary(selected, resolved, out_path):
    kinds = {}
    for r in selected:
        k = row_kind(r["f"])
        kinds[k] = kinds.get(k, 0) + 1
    pages = sorted({p for r in selected if (p := row_page(r["f"])) is not None})
    print("=" * 60)
    print(f"تم إنشاء الخطة المخصصة: {out_path}")
    print(f"عدد الأيام: {len(selected)}")
    print("المقاطع: " + " | ".join(seg["label"] for seg in resolved))
    print(f"الأنواع: حفظ صفحات {kinds.get('حفظ صفحة', 0)}، دوري {kinds.get('دوري', 0)}، "
          f"مراجعات {kinds.get('مراجعة', 0)}، شهادات {kinds.get('شهادة', 0)}")
    if pages:
        print(f"الصفحات: {len(pages)} صفحة ({runs_txt(list_runs(pages))})")
    print(f"النقاط: خام {sum(r['points'] for r in selected)}، "
          f"موزونة {sum(r['points'] * r['weight'] for r in selected)}")
    print("التفاصيل الكاملة في ورقة «الملخص» داخل الملف.")
    print("=" * 60)


def cmd_lookup(args):
    rows = load_rows(args.csv)
    surah_first, surah_last, surah_order, display, juz_rows = build_indices(rows)

    print("=== فهرس السور (بترتيب المصحف كما في الخطة) ===")
    print(f"{'#':>3}  {'السورة':<15} {'أول يوم':>7} {'آخر يوم':>7} {'الأيام':>6}  الأجزاء")
    for i, k in enumerate(surah_order, 1):
        span = [r for r in rows if surah_first[k] <= r["sort"] <= surah_last[k]]
        juzs = sorted({r["juz"] for r in span})
        print(f"{i:>3}  {display[k]:<15} {surah_first[k]:>7} {surah_last[k]:>7} "
              f"{len(span):>6}  {','.join(map(str, juzs))}")
    print()
    print("=== فهرس الأجزاء ===")
    print(f"{'الجزء':>5} {'أول يوم':>8} {'آخر يوم':>8} {'الأيام':>6}  الصفحات")
    for j in sorted(juz_rows):
        day_list = juz_rows[j]
        ps = [p for r in rows if r["juz"] == j
              and (p := row_page(r["f"])) is not None]
        pages_txt = f"{min(ps)}–{max(ps)}" if ps else "—"
        print(f"{j:>5} {day_list[0]:>8} {day_list[-1]:>8} {len(day_list):>6}  {pages_txt}")


def cmd_build(args):
    rows = load_rows(args.csv)
    with open(args.spec, encoding="utf-8") as fh:
        spec = json.load(fh)
    indices = build_indices(rows)
    resolved = resolve_segments(spec, rows, indices)
    selected = select_rows(resolved, rows)
    self_check(selected)
    out_path = build_output(selected, resolved, args.out)
    print_summary(selected, resolved, out_path)


def main():
    parser = argparse.ArgumentParser(
        description="مصنع خطط الحفظ — استخراج خطة مخصصة من الخطة الأم")
    parser.add_argument("--csv", default=str(DEFAULT_CSV),
                        help="مسار لقطة الخطة الأم (افتراضياً assets/master_plan.csv)")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("lookup", help="عرض فهرس السور والأجزاء")
    b = sub.add_parser("build", help="بناء خطة مخصصة")
    b.add_argument("--spec", required=True, help="ملف JSON يحتوي segments")
    b.add_argument("--out", required=True, help="مسار ملف الإخراج .xlsx")
    args = parser.parse_args()
    args.csv = Path(args.csv)
    if not args.csv.exists():
        raise SystemExit(f"خطأ: ملف اللقطة غير موجود: {args.csv}")
    if args.command == "lookup":
        cmd_lookup(args)
    else:
        cmd_build(args)


if __name__ == "__main__":
    main()
