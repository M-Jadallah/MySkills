from __future__ import annotations

import importlib.util
import json
import shutil
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


@unittest.skipUnless(shutil.which("libreoffice") or shutil.which("soffice"), "LibreOffice is not installed")
class FontFitIntegrationTests(unittest.TestCase):
    def test_long_hadith_is_shrunk_and_kept_on_one_page(self):
        config = json.loads((ROOT / "config" / "default.json").read_text(encoding="utf-8"))
        repeated = " ".join(["هَذَا نَصٌّ طَوِيلٌ لِاخْتِبَارِ عَدَمِ تَقْسِيمِ الحَدِيثِ بَيْنَ صَفْحَتَيْنِ"] * 34)
        raw = f"كِتَابُ الاخْتِبَارِ\n\n1 - عَنْ أَبِي هُرَيْرَةَ رضي الله عنه قَالَ: «{repeated}»."
        cleaned, _ = mod.clean_source(raw, config["replace_exact"])
        units = mod.parse_units(cleaned, config["title_prefixes_unvocalized"])
        hadith = next(unit for unit in units if unit.kind == "hadith")
        with tempfile.TemporaryDirectory() as td:
            work = Path(td)
            sizes = mod.resolve_unit_font_sizes(units, config, work)
            self.assertLess(sizes[hadith.index], config["body_font_size_pt"])
            _, pages, _ = mod._render_units_for_markers(
                units, config, work, "verification", unit_font_sizes=sizes
            )
            self.assertEqual(pages[hadith.index][0], pages[hadith.index][1])

    def test_reference_hadith_8_uses_full_page_before_font_reduction(self):
        audit = json.loads((ROOT / "examples" / "formatted-example.audit.json").read_text(encoding="utf-8"))
        size = float(audit["layout"]["unit_font_sizes"]["8"])
        page_7 = audit["layout"]["unit_pages"]["7"]
        page_8 = audit["layout"]["unit_pages"]["8"]
        # Regression: v1.1.0 incorrectly reduced this unit to 10.5 pt
        # because it tried to fit it in the leftover space on page 4.
        self.assertGreaterEqual(size, 22.0)
        self.assertEqual(page_8[0], page_8[1])
        self.assertGreater(page_8[0], page_7[0])


if __name__ == "__main__":
    unittest.main()
