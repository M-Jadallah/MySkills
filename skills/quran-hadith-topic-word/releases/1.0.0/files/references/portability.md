# الاستخدام في Codex وOpenCode وClaude Code

الاسم الموحد: `quran-hadith-topic-word`. الحزمة مهارة مستقلة بصيغة `SKILL.md`، ومجلدها يحتوي المراجع والقالب والسكربتات اللازمة. لا تشترط موصلًا بعينه؛ استخدم أدوات البحث وفتح المصادر وتنفيذ الملفات المتاحة في البرنامج المضيف.

## الاستدعاء

| البرنامج | مثال |
|---|---|
| Codex | `$quran-hadith-topic-word اجمع الأدلة عن الصبر` |
| Claude Code | `/quran-hadith-topic-word الصبر` |
| OpenCode V2 | `@quran-hadith-topic-word اجمع الأدلة عن الصبر` |
| OpenCode مع الأمر المرفق | `/quran-hadith-topic-word الصبر` |

في OpenCode استخدم أداة `skill` التي يوفرها الإصدار المضيف: V2 يستعمل الحقل `id`، وV1 يستعمل `name`. لا تفترض اسم الحقل؛ اتبع تعريف الأداة المتاح. الأمر المرفق يطلب من الوكيل تحميل المهارة ولا ينفذ أمر shell أو يغيّر النموذج.

## التثبيت على جهاز آخر

انسخ مجلد `quran-hadith-topic-word` كاملًا، وليس SKILL.md وحده، إلى مكان اكتشاف البرنامج:

- Codex: `~/.agents/skills/quran-hadith-topic-word/` بحسب وثائقه الحالية. بعض الإصدارات، ومنها الإصدار الذي اختُبر على جهاز المستخدم، تقرأ أيضًا `~/.codex/skills/`. لا تثبت نسختين بالاسم نفسه في مسارين يقرؤهما Codex إن لم تكن هناك حاجة.
- Claude Code: `~/.claude/skills/quran-hadith-topic-word/`.
- OpenCode: `~/.config/opencode/skills/quran-hadith-topic-word/`؛ ويقرأ أيضًا مسارات Claude و`.agents` المتوافقة.
- اختياريًا، انسخ `integrations/opencode-command.md` إلى `~/.config/opencode/commands/quran-hadith-topic-word.md` لإتاحة الاستدعاء بالشرطة المائلة.

`~` هو مجلد المستخدم الفعلي في نظام التشغيل. يمكن استخدام مجلد واحد وروابط مجلدات محلية في مسارات البرامج التي تقرؤها، لتتشارك المهارة والتبعيات عند تحديثها. في Windows يمكن إنشاء Junction بموافقة المستخدم على التثبيت، دون تغيير إعدادات عامة أو سياسات صلاحيات البرامج.

## تشغيل أداة الوورد

يلزم Node.js 18 أو أحدث، وPython 3.10 أو أحدث، وخط Traditional Arabic للعرض المطابق. تعتمد أداة البناء على حزمة `docx` بالإصدار المثبّت في `package.json`. من مجلد المهارة، إن لم توجد الحزمة في runtime المضيف أو بجوار المهارة، جهّزها مرة واحدة:

```text
npm ci --omit=dev --ignore-scripts --no-audit --no-fund
```

عند عدم وجود package-lock.json استخدم `npm install` بالخيارات نفسها. لا تنفذ التثبيت في مجلدات runtimes المدارة. الأوامر داخل SKILL.md تعمل من مجلد المهارة؛ من أي مكان آخر مرّر المسارات المطلقة للسكربتات والمدخلات والمخرجات. يحتفظ التثبيت بـ node_modules محليًا ولا يلزم إدراجه عند مشاركة الحزمة.

في Codex فضّل محمّل تبعيات مساحة العمل إن توفر، واستعمل مساري Node/Python اللذين يعيدهما، ومرّر `--modules` إذا كانت حزمة docx في مجلد آخر. في OpenCode وClaude Code استخدم runtimes المتاحة لهما أو البيئة المحلية المستقلة. جميع الفاحصات المرفقة لا تحتاج API أو مفتاح OpenAI.

لعرض الصفحات يمكن استخدام `render_docx.py` إذا وفره المضيف؛ وإلا حوّل الملف بـ Word أو LibreOffice إلى PDF داخلي ثم إلى PNG عبر Poppler. راجع الصور ولا تُسلّم PDF أو PNG بدل نسختَي Word. إذا لم تتوفر أداة العرض، طبّق الفحص البنيوي وصرّح بحدوده.

## نطاق التحقق

وجود المهارة في مسار صحيح يعني أنها مهيأة للاكتشاف، ولا يثبت أن جلسة برنامج مفتوحة قد حمّلتها أو أن صلاحيات البحث والتنفيذ متاحة. حدّث الجلسة أو افتح أخرى إن لم تظهر. لا تغيّر صلاحيات المضيف تلقائيًا، ولا تتجاوز منعًا صريحًا.

مراجع الصيغة ومسارات الاكتشاف والاستدعاء: [Codex](https://learn.chatgpt.com/docs/build-skills)، [Claude Code](https://code.claude.com/docs/en/skills)، [OpenCode V2 Skills](https://opencode.ai/v2/docs/skills/)، [OpenCode V2 Commands](https://opencode.ai/v2/docs/commands/).
