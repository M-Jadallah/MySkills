"""Meaningful data tests; no artifact authoring or runtime marker calls."""
from __future__ import annotations
import itertools
import tempfile
import unittest
from fractions import Fraction
from unittest.mock import patch

import openpyxl

from core import CATALOG,component,group_rows,parse_cell,partition,safe_names,student_plan
from inputs import DEFAULTS,analyze
from planner import PlanError


class ParserTests(unittest.TestCase):
    def test_aliases_and_boundaries(self):
        self.assertEqual(parse_cell('جزء قد سمع'),[{'type':'juz','number':28}])
        self.assertEqual(parse_cell('القصص'),[{'type':'surah','number':28}])
        self.assertEqual(parse_cell('ق'),[{'type':'surah','number':50}])
        self.assertEqual(parse_cell('جزء٢٩+٢٨'),[{'type':'juz','number':29},{'type':'juz','number':28}])
        self.assertEqual(parse_cell('18.22'),[{'type':'juz','number':18},{'type':'juz','number':22}])
        self.assertEqual(parse_cell('من الأنبياء للأحزاب'),[{'type':'surah_range','from':21,'to':33}])

    def test_no_silent_loss(self):
        for text in ['القصص وكلمات غير معروفة','كم صفحة من النمل','20_27','22-30','٢٤ إلى الشورى','آخر آل عمران',0,'المجادلة فقط','صفحات 10_20','صفحات 10 foo 20']:
            with self.subTest(text=text),self.assertRaises(PlanError):parse_cell(text)

    def test_page_ranges(self):
        self.assertEqual(parse_cell('صفحات: (٣٦٢-٤٢١)+(٥٠٣-٥٦١)'),[{'type':'pages','from':362,'to':421},{'type':'pages','from':503,'to':561}])
        self.assertEqual(parse_cell('جزء1 إلى6'),[{'type':'juz_range','from':1,'to':6}])
        self.assertEqual(parse_cell('صفحات 10 حتى 20'),[{'type':'pages','from':10,'to':20}])
        self.assertEqual(parse_cell('سورة 19'),[{'type':'surah','number':19}])
        for text in ['17-20/28','جزء 17 - 20 و 28']:
            with self.assertRaises(PlanError):parse_cell(text)


class InputTests(unittest.TestCase):
    def test_mapped_columns_preserve_header_location(self):
        book=openpyxl.Workbook();sheet=book.active
        sheet.append(['عنوان تمهيدي']);sheet.append([])
        sheet.append(['اسم الطالب','المتوسطة','الضعيفة']);sheet.append(['طالب تحقق',29,None])
        with tempfile.TemporaryDirectory() as directory,patch('inputs.openpyxl.load_workbook',return_value=book),patch('inputs.sha',return_value='test'):
            result=analyze('read-only-test.xlsx',directory,columns={'name':1,'medium':2,'weak':3})
            self.assertTrue(result['ready']);self.assertEqual(len(result['students']),1)
            self.assertEqual(result['students'][0]['source_record'],sheet.title+':4')

    def test_nonstandard_headers_require_explicit_row(self):
        book=openpyxl.Workbook();sheet=book.active
        sheet.append(['مقدمة']);sheet.append([]);sheet.append(['طالب','مستوى أ','مستوى ب']);sheet.append(['طالب تحقق',29,None])
        with tempfile.TemporaryDirectory() as directory,patch('inputs.openpyxl.load_workbook',return_value=book),patch('inputs.sha',return_value='test'):
            result=analyze('read-only-test.xlsx',directory,columns={'name':1,'medium':2,'weak':3},header_row=3)
            self.assertTrue(result['ready']);self.assertEqual(len(result['students']),1)


class PlanTests(unittest.TestCase):
    def test_medium_actual_covered_pages(self):
        p=student_plan('اختبار',[{'type':'juz','number':29}],[],DEFAULTS)
        self.assertEqual([r[4] for r in p['rows']],[5,10,15,2])
        self.assertEqual(p['total_weight'],32)
        self.assertTrue(all(type(r[2]) is not int for r in p['rows']))

    def test_weak_multiplication_and_points(self):
        p=student_plan('اختبار',[],[{'type':'juz','number':29}],DEFAULTS)
        pages=[e for e in p['events'] if e['kind']=='page'];c=[e for e in p['events'] if e['kind']=='cumulative']
        self.assertEqual(len(pages),20);self.assertEqual(len(c),3)
        self.assertTrue(all(e['row'][4]==2 for e in pages));self.assertTrue(all(e['row'][4]==0 and e['row'][3]==20 for e in c))
        self.assertEqual(p['total_weight'],44)

    def test_remainder_and_partial(self):
        c=component('اختبار',[{'type':'pages','from':100,'to':112}],'medium',DEFAULTS)
        self.assertEqual([e['row'][4] for e in c['rows']],[5,13])
        self.assertFalse(any(e['row'][6] for e in c['rows']))

    def test_short_and_missing_points(self):
        p=student_plan('اختبار',[{'type':'surah','number':58}],[],DEFAULTS)
        self.assertEqual(len(p['rows']),1);self.assertEqual(p['rows'][0][4],1);self.assertIsNone(p['rows'][0][3])
        self.assertEqual(p['grouped_rows'],p['rows'])

    def test_rotation_and_cross_overlap(self):
        p=student_plan('اختبار',[],[{'type':'juz','number':16}],DEFAULTS)
        pages=[e['row'][2] for e in p['events'] if e['kind']=='page']
        self.assertEqual(pages,list(range(305,322))+[302,303,304])
        with self.assertRaises(PlanError):student_plan('اختبار',[{'type':'surah','number':19}],[{'type':'surah','number':19}],DEFAULTS)
        p=student_plan('اختبار',[{'type':'surah','number':29}],[{'type':'surah','number':30}],DEFAULTS)
        self.assertTrue(p['rows'])

    def test_triples(self):
        mixed=student_plan('اختبار',[{'type':'juz','number':16}],[{'type':'juz_range','from':17,'to':18}],DEFAULTS)
        self.assertFalse(any(r[9] for r in mixed['rows']))
        weak=student_plan('اختبار',[],[{'type':'juz_range','from':28,'to':30}],DEFAULTS)
        triple=[r for r in weak['rows'] if r[9]]
        self.assertEqual(len(triple),1)
        base=CATALOG['triple_tests'].get('28+29+30')
        self.assertEqual(triple[0][4],2*(base[4] if base else 3))

    def test_sheet_name_collision(self):
        a='أ'*35
        students=[{'name':a+' ب'},{'name':a+' ج'}];safe_names(students)
        self.assertNotEqual(students[0]['sheet_name'],students[1]['sheet_name'])
        self.assertTrue(all(len(s['sheet_name'])<=31 for s in students))


class PartitionTests(unittest.TestCase):
    def independent(self,weights,exceptions):
        n=len(weights);cap=Fraction(sum(weights),8);candidates=[]
        for cuts in itertools.combinations(range(1,n),7):
            points=(0,*cuts,n);groups=list(zip(points,points[1:]))
            if all(sum(weights[a:b])<=cap or exceptions and b==a+1 and weights[a]>cap for a,b in groups[:7]):
                score=tuple(v for a,b in groups[:7] for v in (sum(weights[a:b]),b))
                candidates.append((score,groups))
        return max(candidates)[1] if candidates else None

    def test_bruteforce_maxima(self):
        for weights in [[5,10,15,2]*3,[2,0,2,2,0,2,2,2,2,2],[0]*10,[5,10,15,2,5,10,15,2,5,10,15,2],[4,1,1,1,1,1,1,1,1]]:
            for exceptions in [False,True]:
                self.assertEqual(partition(weights,exceptions),self.independent(weights,exceptions))

    def test_group_semantics_and_short(self):
        rows=[[None,i+1,f'صف{i+1}',20,w,None,None,None,None,None,None] for i,w in enumerate([5,10,15,2]*3)]
        result=group_rows(rows);self.assertEqual(len(result['grouped_rows']),8)
        self.assertTrue(result['allow_oversized_singletons'])
        self.assertEqual(sum(r[4] for r in result['grouped_rows']),96)
        flattened=[]
        for group in result['groups']:flattened.extend(rows[group['source_start']-2:group['source_end']-1])
        self.assertEqual(flattened,rows)
        self.assertEqual(group_rows(rows[:8])['grouped_rows'],rows[:8])


if __name__=='__main__':unittest.main(verbosity=2)
