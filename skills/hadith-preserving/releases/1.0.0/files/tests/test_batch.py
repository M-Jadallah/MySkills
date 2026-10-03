from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("format_hadith_batch", ROOT / "scripts" / "format_hadith_batch.py")
mod = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = mod
assert SPEC.loader is not None
SPEC.loader.exec_module(mod)
CONFIG = json.loads((ROOT / "config" / "default.json").read_text(encoding="utf-8"))


class BatchTests(unittest.TestCase):
    def test_numbered_files_are_sorted_and_merged(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "02 - كتاب الصلاة.txt").write_text(
                "كِتَابُ الصَّلَاةِ\n2 - عَنْ أَبِي هُرَيْرَةَ رضي الله عنه قَالَ: «الثَّانِي».\n",
                encoding="utf-8",
            )
            (root / "01 - كتاب الطهارة.txt").write_text(
                "كِتَابُ الطَّهَارَةِ\n1 - عَنْ عُمَرَ رضي الله عنه قَالَ: «الأَوَّلُ».\n",
                encoding="utf-8",
            )
            books = mod.discover_books(root)
            self.assertEqual([item[0] for item in books], [1, 2])
            results = []
            for order, name, path in books:
                result = mod.process_book_worker({
                    "order": order,
                    "book_name": name,
                    "path": str(path),
                    "config": CONFIG,
                    "max_attempts": 4,
                })
                self.assertEqual(result["status"], "PASS")
                results.append(result)
            units = mod.merge_units(results)
            self.assertEqual(units[0].text, "كِتَابُ الطَّهَارَةِ")
            self.assertEqual(units[2].text, "كِتَابُ الصَّلَاةِ")
            self.assertEqual([unit.index for unit in units], list(range(len(units))))


if __name__ == "__main__":
    unittest.main()
