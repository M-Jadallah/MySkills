from __future__ import annotations

import importlib.util
import json
import re
import tempfile
import unittest
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("format_hadith", ROOT / "scripts" / "format_hadith.py")
mod = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = mod
assert SPEC.loader is not None
SPEC.loader.exec_module(mod)
CONFIG = json.loads((ROOT / "config" / "default.json").read_text(encoding="utf-8"))


class CoreTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.raw = mod.read_utf8(ROOT / "tests" / "fixtures" / "raw-example.txt")
        cls.cleaned, cls.stats = mod.clean_source(cls.raw, CONFIG["replace_exact"])
        cls.units = mod.parse_units(cls.cleaned, CONFIG["title_prefixes_unvocalized"])

    def test_cleaning_removes_footnotes_and_page_furniture(self):
        self.assertNotIn("________________________________________", self.cleaned)
        self.assertNotRegex(self.cleaned, r"عمدة الأحكام.*\(ص:\s*\d+\)")
        self.assertNotRegex(self.cleaned, r"\(\d+\)")
        self.assertEqual(self.stats.page_markers_removed, 6)
        self.assertGreaterEqual(self.stats.footnote_blocks_removed, 6)

    def test_only_requested_salutation_is_replaced(self):
        self.assertNotIn("صلى الله عليه وسلم", self.cleaned)
        self.assertIn("ﷺ", self.cleaned)
        self.assertIn("رضي الله عنه", self.cleaned)
        self.assertIn("رضي الله عنهم", self.cleaned)

    def test_page_interrupted_hadith_is_rejoined(self):
        self.assertIn("ثُمَّ غَسَلَ وَجْهَهُ", self.cleaned)
        self.assertIn("فَمَضْمَضَ وَاسْتَنْشَقَ", self.cleaned)

    def test_parser_preserves_numbers_and_title(self):
        self.assertEqual(sum(u.kind == "title" for u in self.units), 1)
        hadiths = [u for u in self.units if u.kind == "hadith"]
        self.assertEqual([u.hadith_number for u in hadiths], [str(i) for i in range(1, 9)])
        mod.audit_unit_preservation(self.cleaned, self.units)

    def test_color_segmentation(self):
        text = "6 - عَنْ أَبِي هُرَيْرَةَ رضي الله عنه قَالَ: «نَصُّ الحَدِيثِ». وَلَهُ فِي حَدِيثِ عَبْدِ اللَّهِ بْنِ مُغَفَّلٍ رضي الله عنه"
        segments = mod.style_segments(text)
        role_text = {}
        for chunk, role, _ in segments:
            role_text.setdefault(role, "")
            role_text[role] += chunk
        self.assertIn("6 -", role_text["number"])
        self.assertIn("أَبِي هُرَيْرَةَ", role_text["companion"])
        self.assertIn("عَبْدِ اللَّهِ بْنِ مُغَفَّلٍ", role_text["companion"])
        self.assertNotIn("فِي حَدِيثِ", role_text["companion"])
        self.assertIn("«نَصُّ الحَدِيثِ»", role_text["matn"])

    def test_docx_contains_reference_font_and_colors(self):
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "out.docx"
            mod.build_document(self.units[:3], CONFIG, out, debug_markers=False)
            from zipfile import ZipFile
            with ZipFile(out) as zf:
                xml = zf.read("word/document.xml").decode("utf-8")
            self.assertIn('w:ascii="Traditional Arabic"', xml)
            self.assertIn('w:val="48"', xml)
            self.assertIn('w:val="5B2C06"', xml)
            self.assertIn('w:val="0000CC"', xml)
            self.assertIn('w:fill="D9F2D0"', xml)


if __name__ == "__main__":
    unittest.main()
