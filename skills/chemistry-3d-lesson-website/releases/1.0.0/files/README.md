# مهارة إنشاء دروس الكيمياء التفاعلية ثلاثية الأبعاد

اسم المهارة:

`chemistry-3d-lesson-website`

تحوّل هذه المهارة ملف درس كيمياء إلى موقع تعليمي عربي متكامل، يتضمن شرحًا منظمًا، ورسومًا ومحاكيات علمية ثلاثية الأبعاد، وواجهتين احترافيتين لسطح المكتب والهاتف، واختبارات علمية وتقنية فعلية قبل التسليم.

## ما الذي تتضمنه الحزمة؟

- `SKILL.md`: التعليمات الرئيسة التي يقرأها الوكيل.
- `references/`: ملفات مرجعية تفصيلية تُحمّل عند الحاجة.
- `templates/`: مخططات JSON وقوالب تقارير وإعدادات.
- `scripts/`: أدوات فحص وتجهيز واختبار وتغليف.
- `browser-tests/`: اختبارات Playwright للمتصفح.
- `examples/`: مثال مختصر للحالة الغازية وأوراكل علمي مستقل.
- `assets/branding/`: مكان مخصص لأصول الهوية عند إنشاء نسخة خاصة.

## تثبيت المهارة داخل وكيل

تختلف طريقة تثبيت المهارات من نظام إلى آخر، لكن البنية العامة هي:

1. انسخ مجلد `chemistry-3d-lesson-skill` كاملًا إلى مجلد المهارات الذي يقرأه الوكيل.
2. أبقِ ملف `SKILL.md` في جذر المجلد.
3. لا تفصل مجلدات `references` و`scripts` و`templates` عن المهارة.
4. أعد تشغيل الوكيل أو أعد تحميل قائمة المهارات.
5. اطلب من الوكيل استخدام مهارة `chemistry-3d-lesson-website` وأرفق ملفات الدرس والمشروع المرجعي.

## الملفات التي تُعطى للوكيل مع كل درس

الأفضل إرفاق:

1. ملف الدرس الجديد.
2. أحدث ملف ZIP للموقع المرجعي المعتمد.
3. أحدث ملف HTML مستقل للموقع المرجعي.
4. الشعارات والصور الخاصة بهوية **الطيف في الكيمياء**.

لا تُرسل نسخًا قديمة متعددة من المشروع المرجعي؛ لأنها قد تسبب خلطًا في الكود والتصميم.

## مثال طلب للوكيل

```text
استخدم مهارة chemistry-3d-lesson-website لتحويل ملف الدرس المرفق إلى موقع تعليمي تفاعلي كامل.
استخدم المشروع المرجعي المرفق بوصفه المرجع المعتمد للهوية البصرية والخاتمة وتجربة سطح المكتب والهاتف.
لا تسلّم النتيجة قبل تنفيذ بوابة الاختبارات والإصلاح وإعادة الاختبار الواردة في المهارة.
```

## تشغيل أدوات المهارة

جميع أدوات Python تعتمد على المكتبة القياسية فقط.

### إنشاء هيكل مشروع جديد

```bash
python scripts/init_project.py \
  --output /path/to/new-project \
  --config-template templates/project-config.example.json
```

### جرد ملفات الإدخال

```bash
python scripts/inspect_inputs.py \
  --lesson lesson.pdf \
  --reference-project reference-project \
  --reference-html reference.html \
  --brand-assets brand-assets \
  --output reports/input-inventory
```

### التحقق من خرائط الدرس والتفاعل

```bash
python scripts/validate_maps.py \
  --content-map lesson-content-map.json \
  --interaction-map interaction-map.json
```

### فحص رموز الاتجاه المخفية

```bash
python scripts/check_rtl_unicode.py --path dist --fail-on-found
```

### فحص العمل دون الإنترنت

```bash
python scripts/check_offline_assets.py \
  --path dist \
  --fail-on-remote \
  --fail-on-missing
```

### قفل الخاتمة والتحقق منها

```bash
python scripts/footer_lock.py fingerprint \
  --html approved-reference.html \
  --output templates/footer-lock.json

python scripts/footer_lock.py verify \
  --html dist/lesson-standalone.html \
  --lock templates/footer-lock.json
```

### تشغيل بوابة الجودة

```bash
python scripts/run_quality_gate.py --config project-config.json
```

### إنشاء ملف التسليم المضغوط

```bash
python scripts/package_release.py \
  --project-root . \
  --output release/project.zip \
  --config project-config.json
```

## تشغيل اختبارات المتصفح

```bash
cd browser-tests
npm install
npx playwright install chromium
TARGET_FILE=/absolute/path/to/lesson-standalone.html npm test
```

يمكن بدلًا من ذلك استخدام عنوان خادم محلي:

```bash
TARGET_URL=http://127.0.0.1:4173 npm test
```

## عقد الاختبار داخل الموقع

تتوقع الاختبارات وجود سمات ثابتة مثل:

```html
<section data-lesson-section="section-id">
<div data-science-sim="simulation-id">
<canvas data-simulation-canvas="simulation-id">
<input data-control-id="control-id" data-scientific-variable="T">
<div data-verification-card="simulation-id">
```

التفاصيل الكاملة في:

`references/07-testability-contract.md`

## ملاحظات مهمة

- المهارة لا تحتوي شعارًا أو صورًا شخصية فعلية؛ أضف الأصول المرخصة في نسخة المشروع الخاصة بك.
- لا يجوز للوكيل الادعاء بأن الاختبارات نجحت دون تشغيلها فعليًا.
- إذا تعذر تنفيذ اختبار، يجب تسجيله بوصفه غير منفذ، لا بوصفه ناجحًا.
- أول نسخة تعمل تُعد نسخة مرشحة للاختبار وليست النسخة النهائية.
