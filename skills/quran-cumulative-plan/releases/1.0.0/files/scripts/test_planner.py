"""Behavioral regression tests for the Quran plan contract."""
import unittest

try:
    import planner
except ModuleNotFoundError:
    planner = None


class PlannerTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(planner, 'The reusable plan generator is not implemented yet')

    def make(self, segments, n=5, **extra):
        return planner.build_plan({'student_name': 'أحمد محمد', 'segments': segments, 'cumulative_pages': n, **extra})

    def test_baqarah_batch_grows_from_start(self):
        result = self.make([{'type': 'surah', 'name': 'البقرة'}])
        labels = [r[2] for r in result['rows']]
        self.assertEqual(labels[:12], [2, 3, 4, 5, 6, 'تسميع (2 - 6)', 7, 8, 9, 10, 11, 'تسميع (2 - 11)'])
        self.assertEqual(labels[-9:], [42, 43, 44, 45, 46, 47, 48, 49, 'تسميع سورة البقرة'])
        self.assertEqual(len(labels), 57)
        self.assertTrue(all(r[0] is None for r in result['rows']))
        self.assertEqual([r[1] for r in result['rows']], list(range(1, 58)))
        self.assertEqual(result['rows'][-1][3:10], [1500, 3, 1, 1, 'البقرة', None, None])

    def test_remainder_is_merged_and_final_cumulative_removed(self):
        result = self.make([{'type': 'surah', 'name': 'الأنعام'}])
        self.assertEqual(result['units'][0]['batch_sizes'], [5, 5, 5, 8])
        self.assertEqual([r[2] for r in result['rows'] if r[4] == 0], ['تسميع (128 - 132)', 'تسميع (128 - 137)', 'تسميع (128 - 142)'])
        self.assertEqual([r[2] for r in result['rows']][-9:-1], [143, 144, 145, 146, 147, 148, 149, 150])
        self.assertEqual(len(result['rows']), 27)

    def test_different_batch_size_is_not_hardcoded(self):
        result = self.make([{'type': 'surah', 'number': 2}], 7)
        self.assertEqual(result['units'][0]['batch_sizes'], [7, 7, 7, 7, 7, 13])
        self.assertEqual([r[2] for r in result['rows']][:8], [2, 3, 4, 5, 6, 7, 8, 'تسميع (2 - 8)'])
        self.assertEqual(len(result['rows']), 54)

    def test_level_specific_intervals(self):
        result = self.make([{'type': 'surah', 'name': 'طه'}, {'type': 'juz', 'number': 28}], {'surah': 7, 'juz': 5, 'pages': 5})
        self.assertEqual([u['batch_sizes'] for u in result['units']], [[10], [5, 5, 5, 5]])
        self.assertEqual(len(result['rows']), 35)

    def test_raw_pages_keep_final_cumulative_without_false_certificate(self):
        result = self.make([{'type': 'pages', 'from': 10, 'to': 22}])
        self.assertEqual(result['units'][0]['batch_sizes'], [5, 8])
        self.assertEqual([r[2] for r in result['rows'] if r[4] == 0], ['تسميع (10 - 14)', 'تسميع (10 - 22)'])
        self.assertFalse(any(r[6] for r in result['rows']))
        self.assertEqual(len(result['rows']), 15)

    def test_exact_juz_page_range_uses_original_test(self):
        result = self.make([{'type': 'pages', 'from': 542, 'to': 561}])
        self.assertEqual(result['rows'][-1][2:10], ['تسميع جزء قد سمع تراكمي', 600, 2, None, 1, None, 'قد سمع', None])
        self.assertEqual(len(result['rows']), 24)

    def test_accepted_eight_unit_plan_and_blank_id(self):
        result = self.make([{'type': 'surah', 'name': n} for n in ['البقرة', 'الأنعام', 'التوبة', 'مريم', 'طه']] + [{'type': 'juz', 'number': n} for n in [28, 29, 30]])
        self.assertEqual([u['name'] for u in result['units']], ['مريم', 'طه', 'قد سمع', 'تبارك', 'عم', 'البقرة', 'الأنعام', 'التوبة'])
        self.assertEqual(result['summary']['page_rows'], 173)
        self.assertEqual(result['summary']['cumulative_rows'], 24)
        self.assertEqual(result['summary']['certificate_rows'], 9)
        self.assertEqual(len(result['rows']), 206)
        self.assertEqual(sum(r[2] == 312 for r in result['rows']), 2)
        self.assertTrue(all(r[0] is None and len(r) == 11 for r in result['rows']))
        self.assertEqual(result['filename'], 'أحمد محمد.xlsx')

    def test_juz_sixteen_respects_page_305_rotation(self):
        result = self.make([{'type': 'juz', 'number': 16}])
        self.assertEqual([r[2] for r in result['rows'] if type(r[2]) is int], list(range(305, 322)) + [302, 303, 304])
        self.assertEqual(result['rows'][5][2], 'تسميع (305 - 309)')
        self.assertEqual(result['rows'][-1][8], 'السادس عشر')
        self.assertEqual(len(result['rows']), 24)

    def test_raw_range_crossing_rotation_has_no_unrequested_pages(self):
        result = self.make([{'type': 'pages', 'from': 300, 'to': 310}])
        self.assertEqual([r[2] for r in result['rows'] if type(r[2]) is int], [305, 306, 307, 308, 309, 310, 300, 301, 302, 303, 304])
        self.assertEqual(result['rows'][-1][2], 'تسميع (305 - 310) + (300 - 304)')

    def test_ambiguous_overlap_is_not_silently_duplicated(self):
        with self.assertRaisesRegex(planner.PlanError, 'overlap'):
            self.make([{'type': 'surah', 'name': 'مريم'}, {'type': 'juz', 'number': 16}])

    def test_shared_boundary_between_surahs_is_allowed(self):
        result = self.make([{'type': 'surah', 'name': 'مريم'}, {'type': 'surah', 'name': 'طه'}])
        self.assertEqual(len(result['rows']), 21)

    def test_multiple_short_surahs_on_same_page_follow_quran_order(self):
        result = self.make([{'type': 'surah', 'number': n} for n in [105, 103, 104]], 1)
        self.assertEqual([r[7] for r in result['rows'] if r[7]], ['العصر', 'الهمزة', 'الفيل'])
        self.assertEqual([r[2] for r in result['rows'] if type(r[2]) is int], [601, 601, 601])
        self.assertEqual(len(result['rows']), 6)

    def test_duplicates_and_arabic_numerals(self):
        result = self.make([{'type': 'surah', 'name': 'البقرة'}, {'type': 'surah', 'name': 'البَقَرَه'}], '٥')
        self.assertEqual(len(result['units']), 1)
        self.assertEqual(len(result['rows']), 57)
        other = self.make([{'type': 'juz', 'number': '٢٨'}])
        self.assertEqual(len(other['rows']), 24)

    def test_short_scope_requires_a_real_decision(self):
        with self.assertRaisesRegex(planner.PlanError, 'too_short'):
            self.make([{'type': 'surah', 'name': 'الماعون'}])
        result = self.make([{'type': 'surah', 'name': 'الماعون'}], allow_short_units=True)
        self.assertEqual(result['rows'][-1][4], 1)
        self.assertEqual(result['rows'][-1][7], 'الماعون')
        self.assertIsNone(result['rows'][-1][3])
        self.assertTrue(result['notices'])

    def test_invalid_inputs_fail_without_inventing_pages(self):
        for n in [0, -1, True, 1.5, 'abc']:
            with self.subTest(interval=n), self.assertRaises(planner.PlanError):
                self.make([{'type': 'surah', 'number': 2}], n)
        for segment in [{'type': 'pages', 'from': 0, 'to': 20}, {'type': 'pages', 'from': 40, 'to': 20}, {'type': 'surah', 'name': 'اسم غير موجود'}]:
            with self.subTest(segment=segment), self.assertRaises(planner.PlanError):
                self.make([segment])

    def test_student_filename_cannot_escape_output_directory(self):
        result = planner.build_plan({'student_name': '../أحمد:محمد', 'segments': [{'type': 'surah', 'number': 2}], 'cumulative_pages': 5})
        self.assertNotIn('/', result['filename'])
        self.assertNotIn('\\', result['filename'])
        self.assertNotIn(':', result['filename'])
        self.assertFalse(result['filename'].startswith('.'))
        with self.assertRaises(planner.PlanError):
            planner.build_plan({'student_name': '   ', 'segments': [{'type': 'surah', 'number': 2}], 'cumulative_pages': 5})


if __name__ == '__main__':
    unittest.main(verbosity=2)
