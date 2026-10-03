# Tests

تشغيل الاختبارات الأساسية:

```bash
python -m unittest discover -s tests -p "test_core.py" -v
```

اختبار التكامل الخاص بتقسيم الصفحات يحتاج LibreOffice:

```bash
python -m unittest discover -s tests -p "test_pagination_integration.py" -v
```
