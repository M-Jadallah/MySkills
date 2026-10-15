# معمارية المشروع النهائية — مختبر الطيف للكيمياء

هذه المعمارية هي الناتج النهائي للمنسّق (المهارة `chem-spectrum-lab`). مبنية لتُرفع على **Coolify** باستخدام **Docker Compose** بلا أي مشاكل.

## شجرة المجلدات النهائية
```
chem-spectrum-lab/
├── docker/
│   ├── docker-compose.yml      ← يُستخدم في Coolify (build-based)
│   ├── Dockerfile.frontend     ← يبني image يحوي frontend/ كاملاً
│   └── nginx.conf              ← يخدم SPA + gzip
├── frontend/                   ← ما يبنيه المختبر فعلياً
│   ├── index.html              ← الرئيسية (من 04)
│   ├── about.html              ← عن المختبر (من 04)
│   ├── contact.html            ← التواصل (من 04)
│   ├── lessons.html            ← قائمة الدروس (من 04)
│   ├── css/site.css
│   ├── shared/                 ← أصول مشتركة (storage/layout/nav/theme)
│   ├── assets/                 ← logo.png / logo-dark.png
│   └── lessons/
│       └── lesson-XX/          ← من المهارة 03 (مختبر منفصل)
│           ├── index.html
│           ├── css/lab-style.css
│           ├── js/{experiment,molecules,charts}.js
│           ├── assets/
│           └── _src/lesson-XX.md   ← المصدر الوحيد (من 01)
│           └── design-XX.md        ← التصميم (من 02)
│           └── lesson-XX.pptx / lesson-XX-print.pdf  ← من 05
│           └── lesson-XX.docx                        ← من 06
├── backend/                    ← محجوز للتطوير المستقبلي
├── database/                   ← محجوز للتطوير المستقبلي
└── README.md
```

## قواعد النشر على Coolify (DO / DON'T)

### ✅ DO
- استخدم **Build Pack: Docker Compose** في Coolify.
- أشر إلى `docker/docker-compose.yml`.
- اجعل الـ compose **build-based** (يبني image عبر Dockerfile) — لا bind mounts.
- ضع أي أسرار/متغيرات (لقاعدة بيانات مستقبلية) في **Environment Variables** بـ Coolify، لا تخبأها في الصورة.
- شغّل `docker compose build` محلياً للتأكد قبل الرفع.
- تأكد أن `nginx.conf` يحوي `try_files` لـ SPA وأن المنفذ الداخلي 80.

### ❌ DON'T
- لا تستخدم `./frontend:/usr/share/nginx/html:ro` (bind mount) في الإنتاج — Coolify لا يملك هذا المسار المحلي.
- لا تخبئ أسراراً في الـ Dockerfile.
- لا تفتح منافذ غير ضرورية.
- لا تعتمد على مجلدات host للبيانات (LocalStorage كافٍ حالياً).

## التحقق قبل الرفع
```bash
cd chem-spectrum-lab
docker compose -f docker/docker-compose.yml config   # يجب أن يمر بدون خطأ
docker compose -f docker/docker-compose.yml build     # يجب أن يبني بنجاح
docker compose -f docker/docker-compose.yml up -d     # اختبار محلي على :3000
```
