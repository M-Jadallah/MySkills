#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import sys

required = {
    "docx": "python-docx",
    "lxml": "lxml",
    "fitz": "PyMuPDF",
}
result = {"python": sys.version.split()[0], "dependencies": {}, "libreoffice": None, "traditional_arabic_font": None}
ok = True
for module, package in required.items():
    present = importlib.util.find_spec(module) is not None
    result["dependencies"][package] = present
    ok &= present
soffice = shutil.which("libreoffice") or shutil.which("soffice")
result["libreoffice"] = soffice
ok &= bool(soffice)
fc_match = shutil.which("fc-match")
if fc_match:
    proc = subprocess.run([fc_match, "Traditional Arabic", "--format=%{family}"], text=True, capture_output=True)
    family = proc.stdout.strip()
    result["traditional_arabic_font"] = family
    if "Traditional Arabic" not in family:
        result["font_warning"] = "Traditional Arabic is not installed; the DOCX still requests it, but local rendering may use a fallback."
else:
    result["traditional_arabic_font"] = "fontconfig unavailable; check manually"
print(json.dumps(result, ensure_ascii=False, indent=2))
raise SystemExit(0 if ok else 1)
