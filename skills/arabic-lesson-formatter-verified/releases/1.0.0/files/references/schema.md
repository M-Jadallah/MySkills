# العقد ٤ والأوامر
شغّل `node <skill-dir>/cli.js` ثم الأمر. استخدم مسارات مطلقة؛ لا ترسل السكربتات أو المستند الكامل للنموذج عند تصحيح موضع.

## الإدخال
الدرس: title أو bookTitle وlessonTitle، وparagraphs. الفقرة: type من heading1/heading2/paragraph/bullet/summary/closing، وtext أو runs فقط؛ sourceIds للمتن، level:0 للرئيسية و1 للتابعة تحت العناوين. dependsOn اختياري: معرفات فقرات مرتبطة علميًا تحتاج مراجعة مشتركة. لا تعلق كل الفقرات ببعضها احتياطًا.
المقطع: text، وbold اختياري، وcolor:EE0000 أوshading:D9F2D0. التعليقات notes:[{text,runId?}]؛ ويمكن runIds لمقاطع متتالية. دون مرساة يتعلق التعليق بالفقرة. omissions:[{sourceId,reason}] للحشو فقط.
prepare يولد version:4 وsourceHash ومعرفات الفقرات والمقاطع والتعليقات وعدّادات ids. لا تنسخ البصمة يدويًا ولا تعيد ترقيم العناصر ولا تحذف سجل ids؛ يمنع إعادة استخدام معرف محذوف. عند إضافة عنصر اترك id ليولَّد آليًا.

## الواجهة
- init source.txt source.json [previous-source.json]: حفظ المصدر وتقسيمه ومطابقة الوحدات القديمة. عند غياب الوسيط الثالث يستخدم source.json السابق إن وجد. إذا تعذرت مطابقة نص مكرر يُعطى معرف جديد؛ راجع الروابط قبل prepare.
- prepare draft.json source.json lesson.json: توليد المعرفات والبصمة. لا يعد نجاحه تحققًا من صحة الروابط؛ شغّل check.
- check lesson.json source.json: ملخص وتقرير تفصيلي lesson.json.check.json، وسجل تحذيرات lesson.json.warnings.json.
- inspect lesson.json source.json p2,p4 [state.json|-] [offset=0] [limit=6000]: فقرة ومقاطع وبصمات، وعنوان القسم والسابق واللاحق والمصدر والعلاقات. source:u1,u2 يعرض وحدات مصدر وجوارها. changed مع ملف الحالة يعرض الفقرات التي تحتاج مراجعة.
الإخراج payload جزء JSON متصل، مع nextOffset؛ اجمع الأجزاء بالترتيب حتى null عند الحاجة. لا تفترض أن الصفحة الأولى هي كامل السياق.
- apply lesson.json patch.json source.json: تحقق من كل البصمات على نسخة البداية، ثم طبق المجموعة واحفظها فقط بعد اجتياز الفحص.
- build lesson.json source.json output.docx
- preview output.docx preview.pdf
- status output.docx.state.json: المراجعات المطلوبة دون طباعة النص.
- review state.json content|language|notes "دليل المراجعة" p2,p4: يعتمد المحدد فقط. --all بديل صريح بعد مراجعة الجميع.
- review state.json coherence|visual "دليل المراجعة": ترابط الدرس أو العرض النهائي كاملًا.
- warning lesson.json source.json warningId correct_in_context|corrected|commented|needs_review "الدليل" [noteId]: commented يتطلب تعليقًا موجودًا؛ corrected يتطلب زوال التحذير من النسخة الحالية.

## التصحيحات
كل عملية {op,id,expected,value?}؛ id للفقرة، وrunId أوnoteId للهدف الأصغر. expected بصمة الهدف الذي تعرضه inspect؛ لا تُحسب يدويًا.
- run-text: value نص المقطع الجديد.
- run-format: value حقول bold/color/shading فقط؛ null يزيل الخاصية.
- add-note: value تعليق جديد بلا id؛ البصمة للفقرة.
- update-note/delete-note: noteId وبصمة التعليق؛ update-note يسمح text/runId/runIds.
- source: value قائمة sourceIds؛ البصمة للفقرة.
- split-run: value مصفوفة مقاطع بلا معرفات، مجموع نصوصها يساوي النص السابق حرفيًا. يحفظ معرف الأول ويولد البقية ويوسع التعليقات لتغطي النص الأصلي كاملًا.
- update: تعديل حقول فقرة؛ replace استبدالها مع حفظ id؛ delete حذفها؛ insert إضافة فقرة بعد الهدف بلا id؛ move نقل الفقرة بعد afterId موجود.
مثال: [{"op":"run-text","id":"p2","runId":"r1","expected":"البصمة_من_inspect","value":"نَصٌّ مُصَحَّحٌ"}].
اجمع تعديل النص وتعديل تنسيق الحقل الآخر في مجموعة واحدة. تعديلان للحقل نفسه، وحذف العنصر وتعديله، واستهداف عنصر أُنشئ في المجموعة نفسها تُرفض. التصحيحات تبقى على القرص حتى نجاحها؛ لا تعِد إرسال الفقرة كاملة لتغيير كلمة في مقطع.
