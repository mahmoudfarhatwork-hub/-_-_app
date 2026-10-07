# التطبيق الإسلامي — مستودع المحتوى والأدوات

مستودع المرحلة صفر: خط إنتاج المحتوى الديني (JSON + schema + فحص آلي + بناء قاعدة SQLite)
قبل بناء تطبيق Flutter. الفكرة: أي حديث أو ذكر يدخل التطبيق لازم يعدي على فحص آلي
ومراجعة شرعية عبر Pull Request، ولا يُنشر إلا لو حالته `published`.

## الهيكل

```
.github/
  CODEOWNERS                  المراجع الشرعي (لازم تحط اسمه الحقيقي)
  workflows/content-check.yml فحص المحتوى + الاختبارات + بناء القاعدة عند كل PR
content/
  schema/                     JSON Schema للحديث والذكر
  hadith/                     ملفات الأحاديث (كل ملف مصفوفة عناصر)
  adhkar/                     ملفات الأذكار
docs/
  MVP.md                      نطاق النسخة الأولى والمراحل
  CONTENT_RULES.md            ضوابط المحتوى (من وثيقتك + تعديلات المراجعة)
  SOURCES.md                  المصادر وحالة التحقق من ترخيص كل مصدر
tools/
  common.py                   تحميل المحتوى والفحص وتطبيع النص العربي
  validate_content.py         سكربت الفحص
  build_db.py                 بناء قاعدة SQLite مع بحث FTS5
tests/                        اختبارات unittest
```

## التشغيل

```bash
pip install -r tools/requirements.txt

python -m unittest discover -s tests -v     # الاختبارات
python -m tools.validate_content            # فحص المحتوى
python -m tools.build_db --include-draft    # قاعدة للتطوير تشمل المسودات
python -m tools.build_db                    # قاعدة الإصدار: المنشور فقط
```

الناتج في `build/`.

## إضافة محتوى جديد

1. أضف العنصر في ملف داخل `content/hadith/` أو `content/adhkar/` بحالة `draft`.
2. شغّل `python -m tools.validate_content` وصلّح أي خطأ.
3. افتح Pull Request. المراجع الشرعي (CODEOWNERS) يتحقق من النص والتخريج والدرجة من مصدر مرخّص.
4. بعد الموافقة يضيف المراجع `reviewer` و`reviewed_at` ويغيّر الحالة إلى `published`.

## البحث

البحث على نص مُطبَّع (`normalize_arabic`: بدون تشكيل، توحيد الألف والياء والهاء) عبر FTS5 بـ tokenizer من نوع `trigram`،
فبيلاقي «النيات» داخل «بالنيات». القيد: الاستعلام لازم 3 حروف فأكتر، ولازم التطبيق يطبّع كلمة البحث بنفس الدالة.
الـ tokenizer ده محتاج SQLite 3.34 أو أحدث؛ اتأكد إن نسخة SQLite المضمّنة في Drift/Flutter تدعمه قبل ما تعتمد عليه.

## ما اتفحص وما لم يتفحص

- الفحص الآلي يضمن اكتمال الحقول (الراوي، المصدر، الرقم، الدرجة) ومنع الضعيف والموضوع خارج قسم التحذير. هو **لا** يتحقق من صحة النص أو الدرجة نفسها؛ ده دور المراجع.
- النصوص النموذجية في `content/` مسودات من كتابتي للتجربة، وحالتها `draft`. لا تُنشر قبل مطابقتها بمصدر مرخّص.
- ترخيص كل مصدر في `docs/SOURCES.md` لم يُفتح ويُراجع بعد.

## الخطوة التالية

مشروع Flutter في مجلد `app/` (حزم `adhan` و`flutter_qiblah` و`hijri` و`drift`) بعد ما تثبّت Flutter على جهازك.
