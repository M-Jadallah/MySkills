# توزيع سلسلة مهارات "مختبر الطيف للكيمياء"

هذه السلسلة (7 مهارات) تحوّل درس كيمياء أردني توجيهي (PDF) إلى منظومة كاملة:
Markdown شامل ← تصميم تفاعلي ← مختبر ويب ← موقع متكامل ← سلايدات PPTX ← ملف Word ← حزمة Docker جاهزة للنشر على Coolify.

## للمستخدم النهائي (تثبيت بنقرة واحدة)

امنح المستخدم ملف `chem-spectrum-lab` بالكامل (المجلد الذي يحوي `SKILL.md` + `scripts/` + `references/`)، ثم يشغّل:

```bash
python chem-spectrum-lab/scripts/install.py
```

المنصّب سيقوم بـ:
1. نسخ الـ 7 مهارات إلى `~/.hermes/skills/chem-spectrum-lab/`.
2. تثبيت التبعيات: `pymupdf, python-pptx, python-docx, arabic-reshaper, python-bidi, matplotlib, reportlab, pillow, cairosvg`.
3. توليد الشعار (`logo.png` / `logo-dark.png`).
4. فحص سلامة المهارات (frontmatter + سكريبتات).

بعد إعادة تشغيل جلسة Hermes، يكفي الأمر:
> "شغّل مختبر الطيف لدرس 03 من ملف C:/.../lesson.pdf"

## ملاحظات النشر
- المهارات شخصية محلية (لا تُنشر في repo hermes-agent الرسمي).
- كل درس يُضاف **درساً درساً** بالترتيب الصحيح للكتاب الأردني.
- الأنيميشن الخرافي مُفعّل على سطح المكتب؛ الجوال يحصل على نسخة خفيفة تلقائياً.
- حزمة `docker/` جاهزة للرفع على Coolify (Build Pack: Docker Compose) دون أي تعديل.
