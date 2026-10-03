# -*- coding: utf-8 -*-
"""
توليد خطة وورد يومية لطالب من خطط «مصنع الورد» (ملف Excel) حسب قالب Word المعتمد.

المنطق المقفول مع المستخدم:
- المنجز = كل عناصر الخطة من بدايتها (id=1) حتى موقع آخر صفحة أُنجز (شاملة).
- القسمة = عدد الصفحات المنجزة ÷ عدد الأيام المطلوبة، والزيادة توزع على الأيام الأولى.
- التقطيع بترتيب الخطة (عمود id)، واليوم الواحد قد يحوي عدة رنجات.
- أول مقرر <- تاريخ البدء (أو أول يوم دوام تالٍ إن كان يوم راحة)، ثم كل مقرر
  في أول يوم دوام متتابع.
- عمود «اليوم» = اسم يوم الأسبوع الموافق للتاريخ.
- عدد صفوف الجدول = عدد الأيام بالضبط (إضافة/حذف صفوف عن قالب الـ15 صفاً).
"""
import argparse
import copy
import datetime
import os
import re
import sys
import unicodedata

import openpyxl
import docx
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Pt

DEFAULT_PLANS = r"C:\My-Project\مصنع الورد\docs\خطط مصنع الورد.xlsx"
DEFAULT_TEMPLATE = r"C:\My-Project\مصنع الورد\docs\قالب الوورد للخطة.docx"
DEFAULT_OUTDIR = r"C:\My-Project\مصنع الورد\المخرجات"

TOTAL_PAGES = 604

WEEKDAY_AR = {
    0: "الاثنين",
    1: "الثلاثاء",
    2: "الأربعاء",
    3: "الخميس",
    4: "الجمعة",
    5: "السبت",
    6: "الأحد",
}

# المفاتيح بعد التطبيع (أإآ->ا، ة->ه، ى->ي)
DAY_ALIASES = {
    "السبت": 5,
    "الاحد": 6,
    "الاثنين": 0,
    "الإثنين": 0,
    "الثلاثاء": 1,
    "الاربعاء": 2,
    "الأربعاء": 2,
    "الخميس": 3,
    "الجمعه": 4,
    "الجمعة": 4,
}


class UserError(Exception):
    """خطأ واضح موجّه للمستخدم (يُعرض كما هو بدون تتبع مكدس)."""


def norm(s):
    """تطبيع النص العربي للمطابقة: توحيد الهمزات والتاء المربوطة والألف المقصورة."""
    s = unicodedata.normalize("NFKC", str(s)).strip()
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    s = s.replace("أ", "ا").replace("إ", "ا").replace("آ", "ا")
    s = s.replace("ى", "ي").replace("ة", "ه")
    s = re.sub(r"\s+", " ", s)
    return s


def ranges_of(seq):
    """تقسيم تتابع الصفحات إلى رنجات متصلة: [(بداية, نهاية), ...]."""
    if not seq:
        return []
    ranges = []
    start = prev = seq[0]
    for x in seq[1:]:
        if x != prev + 1:
            ranges.append((start, prev))
            start = x
        prev = x
    ranges.append((start, prev))
    return ranges


def format_ranges(seq):
    """صيغة المقرر المعتمدة: «من صفحة X إلى صفحة Y ومن صفحة Z إلى صفحة W»."""
    parts = []
    for a, b in ranges_of(seq):
        parts.append(f"من صفحة {a} إلى صفحة {b}" if a != b else f"صفحة {a}")
    # كل جزء يبدأ بـ«من» أصلاً، فيكفي الواو للضم: «... إلى 604 ومن صفحة 305...»
    return " و".join(parts)


def load_plan(plans_path, plan_name):
    """تحميل ورقة الخطة المطلوبة وإرجاع قائمة الصفحات بترتيب id (items[id-1])."""
    if not os.path.exists(plans_path):
        raise UserError(f"ملف الخطط غير موجود: {plans_path}")
    wb = openpyxl.load_workbook(plans_path, data_only=True, read_only=True)
    try:
        target = norm(plan_name)
        lookup = {norm(name): name for name in wb.sheetnames}
        if target not in lookup:
            valid = "\n".join(f"  - {n}" for n in wb.sheetnames)
            raise UserError(
                f"اسم الخطة «{plan_name}» غير موجود. الأسماء الصحيحة:\n{valid}"
            )
        real_name = lookup[target]
        ws = wb[real_name]
        items = []
        for row in ws.iter_rows(min_row=2, max_col=1, values_only=True):
            v = row[0]
            if v is None:
                continue
            items.append(int(float(v)))
    finally:
        wb.close()
    if len(items) != TOTAL_PAGES or set(items) != set(range(1, TOTAL_PAGES + 1)):
        raise UserError(f"الخطة «{real_name}» غير سليمة (ليست تعتيباً كاملاً لصفحات 1-{TOTAL_PAGES}).")
    return real_name, items


def parse_date(s):
    s = str(s).strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%Y/%m/%d", "%d.%m.%Y"):
        try:
            return datetime.datetime.strptime(s, fmt).date()
        except ValueError:
            pass
    raise UserError(
        f"تاريخ غير مفهوم: «{s}». الصيغ المقبولة: 2026-09-14 أو 14/09/2026 أو 14-09-2026"
    )


def parse_workdays(s):
    days = set()
    unknown = []
    for token in re.split(r"[,،\s]+", str(s).strip()):
        if not token:
            continue
        n = norm(token)
        if n in DAY_ALIASES:
            days.add(DAY_ALIASES[n])
        else:
            unknown.append(token)
    if unknown:
        valid = "، ".join(WEEKDAY_AR[i] for i in range(7))
        raise UserError(f"أيام دوام غير معروفة: {'، '.join(unknown)}. الأيام الصحيحة: {valid}")
    if not days:
        raise UserError("لم تُحدد أيام دوام. مثال: «السبت، الأحد، الاثنين، الثلاثاء، الأربعاء»")
    return days


def first_working_day(start, workdays):
    d = start
    while d.weekday() not in workdays:
        d += datetime.timedelta(days=1)
    return d


def next_working_day(d, workdays):
    d = d + datetime.timedelta(days=1)
    while d.weekday() not in workdays:
        d += datetime.timedelta(days=1)
    return d


def build_schedule(items, last_page, num_days):
    """إرجاع (completed, counts) حيث counts = عدد صفحات كل يوم بالترتيب."""
    if not (1 <= last_page <= TOTAL_PAGES):
        raise UserError(f"رقم الصفحة {last_page} خارج المدى الصحيح (1-{TOTAL_PAGES}).")
    if num_days < 1:
        raise UserError("عدد الأيام المطلوبة يجب أن يكون 1 على الأقل.")
    try:
        pos = items.index(last_page)  # موقع آخر صفحة أُنجز في ترتيب الخطة
    except ValueError:
        raise UserError(f"الصفحة {last_page} غير موجودة في الخطة.")
    completed = items[: pos + 1]
    if num_days > len(completed):
        raise UserError(
            f"عدد الأيام المطلوبة ({num_days}) أكبر من عدد الصفحات المنجزة "
            f"({len(completed)}) — لا يمكن توزيع أقل من صفحة واحدة لكل يوم."
        )
    base, rem = divmod(len(completed), num_days)
    counts = [base + 1] * rem + [base] * (num_days - rem)
    return completed, counts


def set_paragraph_text(p, text):
    """استبدال نص فقرة مع الحفاظ على تنسيق أول run (لحقول {{...}})."""
    if p.runs:
        p.runs[0].text = text
        for r in p.runs[1:]:
            r.text = ""
    else:
        p.add_run(text)


def replace_placeholder(doc, placeholder, value):
    """استبدال حقل {{...}} في كل فقرات المتن وخلايا الجداول."""
    replaced = False
    for p in doc.paragraphs:
        if placeholder in p.text:
            set_paragraph_text(p, p.text.replace(placeholder, value))
            replaced = True
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                for p in cell.paragraphs:
                    if placeholder in p.text:
                        set_paragraph_text(p, p.text.replace(placeholder, value))
                        replaced = True
    return replaced


def fill_cell(cell, text):
    """تعبئة خلية بيانات: توسيط + حجم 14pt (sz و szCs) + اتجاه RTL للنص."""
    p = cell.paragraphs[0]
    for extra in cell.paragraphs[1:]:
        extra._p.getparent().remove(extra._p)
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run(str(text))
    rPr = run._r.get_or_add_rPr()
    sz = OxmlElement("w:sz")
    sz.set(qn("w:val"), "28")  # 14pt
    rPr.append(sz)
    szCs = OxmlElement("w:szCs")
    szCs.set(qn("w:val"), "28")
    rPr.append(szCs)
    rtl = OxmlElement("w:rtl")
    rPr.append(rtl)
    tcPr = cell._tc.get_or_add_tcPr()
    if tcPr.find(qn("w:vAlign")) is None:
        vAlign = OxmlElement("w:vAlign")
        vAlign.set(qn("w:val"), "center")
        tcPr.append(vAlign)


def resize_table(table, needed_rows):
    """ضبط عدد صفوف الجدول = needed_rows (إضافة نسخ من آخر صف فارغ أو حذف الأواخر)."""
    while len(table.rows) > needed_rows:
        tr = table.rows[-1]._tr
        tr.getparent().remove(tr)
    while len(table.rows) < needed_rows:
        new_tr = copy.deepcopy(table.rows[-1]._tr)
        table._tbl.append(new_tr)


def generate(args):
    real_plan, items = load_plan(args.plans, args.plan)
    start = parse_date(args.start_date)
    workdays = parse_workdays(args.workdays)
    completed, counts = build_schedule(items, args.last_page, args.days)

    # تقطيع المنجز على الأيام ثم إسناد التواريخ (أيام الدوام فقط)
    schedule = []
    idx = 0
    d = first_working_day(start, workdays)
    for count in counts:
        chunk = completed[idx : idx + count]
        idx += count
        schedule.append((d, chunk))
        d = next_working_day(d, workdays)

    if not os.path.exists(args.template):
        raise UserError(f"ملف القالب غير موجود: {args.template}")
    doc = docx.Document(args.template)

    replace_placeholder(doc, "{{اسم الطالب}}", args.student.strip())
    replace_placeholder(doc, "{{المجموعة}}", args.group.strip())

    table = doc.tables[0]
    resize_table(table, len(schedule) + 1)  # صف العناوين + صف لكل يوم
    for i, (d, chunk) in enumerate(schedule, start=1):
        row = table.rows[i]
        fill_cell(row.cells[0], WEEKDAY_AR[d.weekday()])
        fill_cell(row.cells[1], d.strftime("%d/%m/%Y"))
        fill_cell(row.cells[2], format_ranges(chunk))

    os.makedirs(args.out_dir, exist_ok=True)
    safe_name = re.sub(r'[\\/:*?"<>|]', "", args.student).strip()
    if not safe_name:
        raise UserError("اسم الطالب غير صالح لاستخدامه كاسم ملف.")
    out_path = os.path.join(args.out_dir, f"{safe_name}.docx")
    doc.save(out_path)

    # ملخص للعرض
    lines = []
    lines.append(f"تم إنشاء الملف: {out_path}")
    lines.append(f"الطالب: {args.student.strip()} | المجموعة: {args.group.strip() or '—'}")
    lines.append(f"الخطة: {real_plan}")
    lines.append(
        f"المنجز: {len(completed)} صفحة ({format_ranges(completed)}) موزعة على {args.days} أيام"
    )
    lines.append("الجدول:")
    for i, (d, chunk) in enumerate(schedule, start=1):
        lines.append(f"  {i}) {WEEKDAY_AR[d.weekday()]} {d.strftime('%d/%m/%Y')}: {format_ranges(chunk)}")
    print("\n".join(lines))


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="توليد خطة وورد يومية لطالب")
    parser.add_argument("--student", required=True, help="اسم الطالب")
    parser.add_argument("--plan", required=True, help="اسم الخطة (اسم ورقة Excel)")
    parser.add_argument("--last-page", type=int, required=True, help="آخر صفحة أُنجز (رقم صفحة المصحف)")
    parser.add_argument("--start-date", required=True, help="تاريخ البدء (2026-09-14 أو 14/09/2026)")
    parser.add_argument("--workdays", required=True, help="أيام الدوام مفصولة بفواصل: السبت,الأحد,...")
    parser.add_argument("--days", type=int, required=True, help="عدد الأيام المطلوبة")
    parser.add_argument("--group", default="", help="المجموعة")
    parser.add_argument("--out-dir", default=DEFAULT_OUTDIR, help="مجلد المخرجات")
    parser.add_argument("--plans", default=DEFAULT_PLANS, help="مسار ملف خطط Excel")
    parser.add_argument("--template", default=DEFAULT_TEMPLATE, help="مسار قالب Word")
    args = parser.parse_args()
    try:
        generate(args)
    except UserError as e:
        print(f"خطأ: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
