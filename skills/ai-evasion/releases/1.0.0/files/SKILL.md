---
name: ai-evasion
description: >
  أداة متكاملة لتجنب كشف النص المُولّد بالذكاء الاصطناعي.
  تستند إلى هندسة عكسية لـ 3 نماذج RoBERTa مفتوحة المصدر (OpenAI Detector،
  ChatGPT HC3 Detector، PirateXX) وتُطبّق 12 قاعدة لتحييد 8 إشارات إحصائية
  تلتقطها الكاشفات. تحافظ على المحتوى 100% —— تغيّر فقط البصمة السطحية.
  
  ✓ كشف النص قبل التعديل  ✓ إعادة صياغة ذكية  ✓ برومبت جاهز للوكيل
  ✓ دعم العربية  ✓ تقرير تحليلي للإشارات
trigger: |
  حمّل هذه المهارة عندما يطلب المستخدم:
  - "تجنب كشف AI" / "تفادي كاشفات الذكاء الاصطناعي"
  - "تمويه النص" / "إخفاء البصمة الآلية"
  - "إعادة صياغة لتفادي الكشف"
  - "ai evasion" / "bypass ai detector"
  - "humanize text" / "make text pass as human"
  - أو يرسل مقالاً ويطلب جعله غير قابل للكشف
category: document
---

# 🛡️ AI Evasion — أداة تجنب كاشفات النص المُولّد

## نظرة عامة

هذه المهارة نتاج **هندسة عكسية شاملة** لثلاثة نماذج RoBERTa مفتوحة المصدر لكشف النص المُولّد بالذكاء الاصطناعي:

| النموذج | تحميلات HuggingFace | مُدرَّب على |
|---------|---------------------|-------------|
| `openai-community/roberta-base-openai-detector` | 369,826 | GPT-2 1.5B |
| `Hello-SimpleAI/chatgpt-detector-roberta` | 36,809 | HC3 (37K زوج بشري/ChatGPT) |
| `PirateXX/AI-Content-Detector` | 81,637 | خليط غير موثّق |

**الاكتشاف الأساسي:** جميع النماذج الثلاثة تستخدم RoBERTa-base (125M معامل) مع اختلاف بيانات التدريب فقط. لذلك آلية الكشف **موحّدة**، واستراتيجية التملص الواحدة تعمل ضدها جميعاً.

## الإشارات الثمانية التي تلتقطها الكاشفات

| # | الإشارة | ماذا يرى الكاشف |
|---|---------|-----------------|
| 1 | **توزيع احتمالية الرموز** | AI يهيمن عليه الرموز عالية الاحتمال (أخضر/أصفر في GLTR). البشر يستخدمون كلمات غير متوقعة. |
| 2 | **انتظام طول الجمل** | AI: انحراف معياري ≈5.1. البشر: ≈14.2 (ورقة HC3). |
| 3 | **انتظام الصياغة** | AI يكرر نمط: فاعل→فعل→مفعول. |
| 4 | **علامات الترقيم** | AI: نقطة وفاصلة فقط. البشر: شرطات، فواصل منقوطة، حذف. |
| 5 | **كلمات ربط نمطية** | AI يفرط في Furthermore, Moreover, Additionally (8 أضعاف البشر). |
| 6 | **التنوع المعجمي** | TTR منخفض — تكرار نفس المفردات. |
| 7 | **تماسك مفرط** | AI متماسك جداً — لا استطرادات. |
| 8 | **نبرة موحّدة** | AI: صوت واحد ثابت. البشر: تأرجح بين الرسمي والعفوي. |

## أدوات المهارة

| الملف | الوظيفة |
|-------|---------|
| `scripts/detect.py` | فحص النص وتقرير باحتمالية الكشف + الإشارات الضعيفة |
| `scripts/evade.py` | إعادة صياغة النص لتجنب الكشف (يُطبّق القواعد الـ 12) |
| `references/prompt.md` | البرومبت الكامل الجاهز لإعطائه لأي وكيل |
| `references/detection-signals.md` | مرجع تفصيلي للإشارات الثمانية مع أدلة من الأبحاث |
| `templates/before-after.md` | قالب مقارنة: قبل/بعد تطبيق التمويه |

## سير العمل

### الخطوة 1: فحص النص

```bash
python3 scripts/detect.py "النص المراد فحصه..."
```

يُخرج:
- احتمالية أن النص AI (0-100%)
- أي الإشارات الثمانية هي الأضعف (الأكثر عرضة للكشف)
- توصيات محددة للإصلاح

### الخطوة 2: إعادة الصياغة

```bash
python3 scripts/evade.py input.txt output.txt
```

يُطبّق 12 قاعدة لتحييد الإشارات مع الحفاظ على المحتوى 100%.

### الخطوة 3 (بديل): استخدام البرومبت مع الوكيل

انسخ محتوى `references/prompt.md` وألصقه في بداية المحادثة مع أي وكيل ذكي، متبوعاً بالمقال المطلوب تمويهه.

## القواعد الـ 12 للتمويه

1. حقن 8-12% كلمات منخفضة الاحتمال (منطقة حمراء/بنفسجية في GLTR)
2. فرض تباين عالٍ في أطوال الجمل (انحراف معياري > 12)
3. كسر النمط التركيبي (تنويع بدايات الجمل)
4. حقن علامات ترقيم متنوعة (— ; …)
5. استبدال كلمات الربط الآلية بأخرى "بشرية"
6. فرض تنوع معجمي (TTR > 0.65)
7. إضافة 2-3 استطرادات دقيقة (micro-digressions)
8. تغيير النبرة 3-4 مرات
9. حقن "burstiness" (تجميع جمل متشابهة الطول ثم كسر النمط)
10. إضافة لمسات غير رسمية (contractions، عبارات عفوية)
11. بدايات فقرات غير تقليدية
12. تنويع صياغة الأرقام والإحصائيات

## مثال

**قبل (نص AI خام):**
> The implementation of renewable energy solutions has become increasingly important in recent years. Furthermore, governments around the world have recognized the urgent need to transition away from fossil fuels. Additionally, significant investments have been made...

**بعد (بعد التمويه):**
> Renewable energy? It's gone from niche to non-negotiable — and fast. Governments — some kicking and screaming, others sprinting — are finally pulling the plug on fossil fuels. The money's following. Big time. We're talking investments that would've been unthinkable a decade ago...

## متطلبات

```bash
pip install transformers torch textstat numpy
```

## المصادر العلمية

- **GPT-2 Report** (OpenAI, 2019) — القسم الخاص بالكشف الآلي (صفحة 12)
- **HC3 Paper** (Guo et al., 2023) — How Close is ChatGPT to Human Experts?
- **GLTR** (Gehrmann et al., 2019) — Giant Language Model Test Room (MIT/IBM/Harvard)

## تنبيه أخلاقي

⚠️ صُممت هذه الأداة للاستخدامات المشروعة: حماية خصوصية الكتّاب، اختبار أنظمة الكشف، البحث الأكاديمي في مجال stylometry. لا تُستخدم للغش الأكاديمي أو انتحال الأعمال.
