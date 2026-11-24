# التشغيل والمواصفة

## اعتماديات التنفيذ

استدعِ `load_workspace_dependencies` واحفظ المسارات التي أعادتها الأداة. جميع أوامر Python/Node أدناه تعني التنفيذ بالمفسرات المجمعة، لا مفسرات النظام. المولد يحتاج `@oai/artifact-tool` وقراءة Excel بـopenpyxl، وlxml/Pillow/pdfplumber/pypdf للتدقيق؛ لا يكتب Excel بـopenpyxl. لا يثبّت شيئًا داخل dependencies.

استخرج موقع `render_docx.py` من مهارة المستندات المثبتة؛ يُمرّر بالوسيط `--renderer`. على Windows إن لم يكن LibreOffice على PATH مرّر مسار `soffice.exe` الموجود بـ`--soffice` (غالبًا داخل Program Files/LibreOffice/program). لا تخمّن أن PDF تولّد: تعتمد النتيجة على وجوده وفحصه. العلامات الخاصة بالجداول/Word/PDF تُشغّل وفق المهارات قبل التأليف: ملفان xlsx، وعدد الطلاب لكل من docx/pdf. لا تعِد العلامات عند استئناف مرحلة ضمن العملية ذاتها.

## تحليل قبل التأليف

```text
python SKILL/scripts/pipeline.py analyze --input INPUT.xlsx --work-dir WORK
```

إذا لزم: `--sheet "اسم الورقة"`، أو `--columns '{"name":1,"medium":2,"weak":3}'`؛ الأعمدة مرقمة من1، وصف العناوين يُبحث عنه ضمن أول20 صفًا. تعيين الأعمدة لا يعني أن الصف الأول عناوين. للعناوين غير القياسية حدّد `--header-row 3` مثلًا. أي صيغ في أعمدة المدخلات تُرفض لتجنب قراءتها كنطاقات.

`request.json` يحفظ الملف المطلق وبصمته والورقة والصف والعناوين، وكل سجل بـ`id` ثابت من الورقة ورقم الصف، ونصه الخام وparsed ومشكلات التحليل. **لا تعدّل raw أو parsed أو تحذف سجلًا**؛ الحلول في resolution فقط، ويُعاد مطابقتها بالملف قبل البناء. راجع `possible_duplicates` كذلك؛ هي تنبيهات أسماء متشابهة وليست إذنًا بدمجها. يمكن متابعة الأعمال المستقلة لحين جواب المستخدم؛ لا تنشئ الخطط الناقصة على أنها مكتملة.

مثال resolution على سجل موجود:

```json
{
  "student_name": "الاسم المصحح عند الحاجة",
  "medium": [{"type":"juz","number":29}],
  "weak": [{"type":"surah","number":19}],
  "reason": "اختار المستخدم هذا التصنيف في رسالة التوضيح"
}
```

للسجل المتروك بعد دمجه/اختيار الأحدث:

```json
{"skip":true,"reason":"سجل مكرر؛ اختار المستخدم السجل الأحدث ذي المعرف…"}
```

للمراجعة المستقلة المتداخلة الصريحة: `"overlap_policy":"independent"` مع reason. لا تُفعّلها لمعالجة خطأ دون قرار. لا تعدّل settings إلا لتغيير مأذون به؛ الثوابت في هذه النسخة8 فترات ومعامل الضعيف2 وحذف المختلط. `cumulative_pages` افتراضي5 و`allow_short_units`=true وفق سير العمل المعتمد.

شغّل:

```text
python SKILL/scripts/pipeline.py check --spec WORK/request.json
```

لا تنفّذ build إلا حين `ready:true`. وجود analysis.json لا يعني اكتمال المراجعة البشرية؛ قارن المقترحات بالمدخلات.

## التنفيذ

```text
python SKILL/scripts/pipeline.py build --spec WORK/request.json --work-dir WORK/build --out-dir OUTPUT --node BUNDLED_NODE --node-modules BUNDLED_MODULES --renderer DOCS/render_docx.py --soffice SOFFICE_EXE
```

`--soffice` اختياري. مجلد الإخراج يجب أن يكون جديدًا/فارغًا. المولد ينشئ الحسابات، ثم ملفَي Excel، ويستعيد RTL ويفحصهما، ثم معاينات تغطي جميع الصفوف، ثم Word من ملف التجميع الفعلي، ثم رندرة جميع الطلاب وPDF باسم الطالب والتحقق. `work-dir` منفصل عن out-dir. لا يشترط اسم مسار أو مستخدم أو إصدار runtime ثابتًا.

يمكن تأخير التحويل بعد حفظ Word بعدم تمرير renderer؛ حينها النتيجة `render_pending:true` لا `verified:true`. للتحويل لاحقًا:

```text
python SKILL/scripts/pipeline.py render --job WORK/build/job.json --renderer DOCS/render_docx.py --soffice SOFFICE_EXE
python SKILL/scripts/pipeline.py verify --job WORK/build/job.json
```

إذا تعثرت مرحلة قبل اكتمال Word، لا تعِد build فوق المخرجات ولا تحذفها. استأنف من job.json بعد تصحيح السبب:

```text
python SKILL/scripts/pipeline.py resume --job WORK/build/job.json --node BUNDLED_NODE --node-modules BUNDLED_MODULES --renderer DOCS/render_docx.py --soffice SOFFICE_EXE
```

يتحقق resume من بصمات الملف والمواصفة والأصول ومن تطابق الخطة مع المواصفة، ويستكمل الملفات المملوكة لهذه العملية فقط. إذا تغيرت البيانات ابدأ تحليلًا ومجلد إخراج جديدين. رندرة Excel على Windows قد تخرج برمز1 بعد نجاح كتابة الصور؛ تُقبل فقط بإيصال جديد صحيح لكلا الملفين وPNG صالح لكل نطاق. هذا الاستثناء لا ينطبق مطلقًا على فشل تصدير PDF أو ملف Excel أو نقص إيصال.

لا تعطّل بوابة العرض لتجاوز مشكلة. يكتب work سجلات renderer والمعاينات وضبط الحسابات؛ لا تُسلّم ملفات الدعم. بعد فحص الصور فعلًا:

```text
python SKILL/scripts/pipeline.py package --job WORK/build/job.json --visual-reviewed
```

الحزمة تحتوي ملفَي Excel ومجلدَي Word/PDF، وباسم الطالب الكامل لكل ملف (تنظف الأحرف المحظورة فقط). الوسيط `--visual-reviewed` يؤكد أن فحص المساعد حصل فعلًا؛ لا تستخدمه بديلًا للفحص. يجب نجاح verify مرة أخرى قبل تعبئة الحزمة، ويُتحقق من قائمة الملفات والأسماء والعدد والبصمات.

## تحقق إضافي عند تغيير الحسابات

`test_pipeline.py` يختبر حدود الأسماء ومنع الإسقاط والبواقي واختبارات المتوسط والضعيف والتداخل ودوران الجزء16 وشهادات الثلاثيات، ويقارن التقسيم ببحث شامل مستقل. افحص نتائج حقيقية باختبار الرجوع، ثم مرّر المهارة لاختبار مستقل محدود إذا كان مفيدًا ومسموحًا. لا تضع ملفات طلاب أو بيانات هوياتهم داخل أصول المهارة.

المحقق الرسمي `quick_validate.py` من skill-creator يحتاج PyYAML. إذا غاب من runtime المجمعة، ثبّته في مجلد مؤقت مستقل بـ`python -m pip install --target TASK_DEPS PyYAML` وشغّل المحقق مع PYTHONPATH لذلك المجلد. لا تعدّل dependency directories أو ملف المحقق لتجاوز الفحص.
