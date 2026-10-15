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
class PaginationIntegrationTests(unittest.TestCase):
    def test_part_headers_start_on_fixed_page_intervals(self):
        config = json.loads((ROOT / "config" / "default.json").read_text(encoding="utf-8"))
        config["part_pages"] = 2
        base = (
            "عَنْ أَبِي هُرَيْرَةَ رضي الله عنه قَالَ: قَالَ رَسُولُ اللَّهِ صلى الله عليه وسلم: "
            "«هَذَا نَصٌّ تَجْرِيبِيٌّ طَوِيلٌ لِقِيَاسِ الصَّفَحَاتِ وَفَحْصِ رَأْسِ الجُزْءِ» ."
        )
        raw = "كِتَابُ الاخْتِبَارِ\n\n" + "\n\n".join(f"{i} - {base}" for i in range(1, 17))
        cleaned, _ = mod.clean_source(raw, config["replace_exact"])
        units = mod.parse_units(cleaned, config["title_prefixes_unvocalized"])
        with tempfile.TemporaryDirectory() as td:
            work = Path(td)
            layout = mod.resolve_layout(units, config, work)
            self.assertGreaterEqual(layout.page_count, 3)
            for idx, actual in enumerate(layout.part_start_pages, start=0):
                self.assertEqual(actual, idx * config["part_pages"] + 1)


if __name__ == "__main__":
    unittest.main()
