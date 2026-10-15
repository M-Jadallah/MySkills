from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
import sys
from pathlib import Path
from zipfile import ZipFile

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
        self.assertEqual(sum(unit.kind == "title" for unit in self.units), 1)
        hadiths = [unit for unit in self.units if unit.kind == "hadith"]
        self.assertEqual([unit.hadith_number for unit in hadiths], [str(i) for i in range(1, 9)])
        mod.audit_unit_preservation(self.cleaned, self.units)

    def test_full_narrator_chain_and_all_matn_variants(self):
        text = (
            "9 - حَدَّثَنَا مُحَمَّدُ بْنُ عَبْدِ اللَّهِ، عَنْ أَبِيهِ، عَنْ أَبِي هُرَيْرَةَ رضي الله عنه قَالَ: "
            "«المَتْنُ الأَوَّلُ».\nوَفِي رِوَايَةٍ: «المَتْنُ الثَّانِي»"
        )
        segments = mod.style_segments(text)
        role_text: dict[str, str] = {}
        for chunk, role, _ in segments:
            role_text.setdefault(role, "")
            role_text[role] += chunk
        self.assertIn("مُحَمَّدُ بْنُ عَبْدِ اللَّهِ", role_text["narrator"])
        self.assertIn("أَبِيهِ", role_text["narrator"])
        self.assertIn("أَبِي هُرَيْرَةَ", role_text["narrator"])
        self.assertIn("«المَتْنُ الأَوَّلُ»", role_text["matn"])
        self.assertIn("«المَتْنُ الثَّانِي»", role_text["matn"])

    def test_definition_term_is_bold_only(self):
        text = "1 - عَنْ فُلَانٍ قَالَ: «نَصٌّ».\nالتَّوْرُ: شِبْهُ الطَّسْتِ."
        segments = mod.style_segments(text)
        self.assertIn(("التَّوْرُ:", "isnad", True), segments)
        meaning = next(item for item in segments if "شِبْهُ الطَّسْتِ" in item[0])
        self.assertEqual(meaning[1:], ("isnad", False))

    def test_docx_is_table_free_and_contains_heading_border(self):
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "out.docx"
            mod.build_document(self.units[:3], CONFIG, out, debug_markers=False)
            with ZipFile(out) as archive:
                xml = archive.read("word/document.xml").decode("utf-8")
            self.assertNotIn("<w:tbl>", xml)
            self.assertIn('w:ascii="Traditional Arabic"', xml)
            self.assertIn('w:val="48"', xml)
            self.assertIn('w:val="5B2C06"', xml)
            self.assertIn('w:val="0000CC"', xml)
            self.assertIn('w:val="C00000"', xml)
            self.assertIn('w:fill="D9F2D0"', xml)
            self.assertIn("<w:pBdr>", xml)
            self.assertIn('w:color="000000"', xml)
            self.assertIn("<w:keepLines", xml)


if __name__ == "__main__":
    unittest.main()
