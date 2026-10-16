"""Regression tests for multi-source provenance/merge gates; no Word or model calls."""
import argparse
import copy
import json
import shutil
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path
from course_model import compile_course, read_json, load_run, digest
from prepare_course import prepare

SKILL = Path(__file__).resolve().parents[1]
WORK = None


class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=WORK, prefix='pipeline-')
        self.root = Path(self.temp.name)
        self.run = self.root/'run'
        shutil.copytree(SKILL/'assets/sample-course', self.run)
        self.manifest = self.run/'manifest.json'
        self.data = read_json(self.run/'course.json')

    def tearDown(self):
        self.temp.cleanup()

    def fail_course(self, data=None):
        with self.assertRaises((ValueError, OSError)):
            compile_course(data if data is not None else self.data, self.manifest)

    def test_complete_course(self):
        doc, text, report = compile_course(self.data, self.manifest)
        self.assertEqual(report['sources'], 3)
        self.assertEqual(report['worker_units'], len(doc['coverage']['units']))
        self.assertEqual(report['integrated_facts'], 10)
        self.assertIn('الماضي', text)
        self.assertTrue(any('anchor' in s for t in doc['topics'] for b in t['blocks'] if b['type']=='paragraph' for s in b['text'] if isinstance(b['text'], list)))

    def test_missing_worker(self):
        (self.run/'analyses/l002.json').unlink()
        self.fail_course()

    def test_snapshot_changed(self):
        p=self.run/'sources/l001.original.txt'
        p.write_bytes(p.read_bytes()+b'x')
        self.fail_course()

    def test_normalized_source_changed(self):
        p=self.run/'sources/l001.txt'
        p.write_bytes(p.read_bytes()+b'x')
        self.fail_course()

    def test_stale_worker(self):
        p=self.run/'analyses/l001.json'
        p.write_bytes(p.read_bytes()+b'\n')
        self.fail_course()

    def test_missing_unit(self):
        self.data['integration']['facts'][0]['members']=[]
        self.fail_course()

    def test_duplicate_unit(self):
        self.data['integration']['facts'][1]['members'].append(copy.deepcopy(self.data['integration']['facts'][0]['members'][0]))
        self.fail_course()

    def test_unreviewed_relation(self):
        self.data['integration']['decisions'].pop()
        self.fail_course()

    def test_broken_overview(self):
        self.data['topics'][0]['blocks'][0]['root']['children'][0]['topic_ref']='missing'
        self.fail_course()

    def test_inconsistent_concept_label(self):
        self.data['integration']['concepts'][0]['label']='مُخْتَلِفٌ'
        self.fail_course()

    def test_missing_summary(self):
        self.data['integration']['facts'][0]['summary_refs']=[]
        self.fail_course()

    def test_correction_cannot_remain_primary(self):
        for fact in self.data['integration']['facts']:
            for member in fact['members']:
                if member['role']=='corrected':
                    member['role']='primary'
                    member.pop('correction_id')
        self.fail_course()

    def test_wrong_correction_target(self):
        self.data['integration']['corrections'][0]['replacement_units']=['l001::u1']
        self.fail_course()

    def test_malformed_worker(self):
        p=self.run/'analyses/l001.json'
        worker=read_json(p)
        worker['concepts']=[None]
        p.write_text(json.dumps(worker),encoding='utf-8')
        with self.assertRaises(ValueError):
            load_run(self.manifest)

    def test_path_escape(self):
        data=read_json(self.manifest)
        data['sources'][0]['analysis_path']='../outside.json'
        self.manifest.write_text(json.dumps(data),encoding='utf-8')
        self.fail_course()

    def test_navigation_ids_are_safe(self):
        self.data['topics'][0]['blocks'].append({'id':'course_nav_1','type':'paragraph','text':'بَيَانٌ'})
        doc,_,_=compile_course(self.data,self.manifest)
        ids=[b['id'] for t in doc['topics'] for b in t['blocks']]
        self.assertEqual(len(ids),len(set(ids)))
        self.assertTrue(all(len('lm_'+i)<=40 for i in ids))

    def test_prepare_order_encodings_and_no_overwrite(self):
        paths=[]
        for name,encoding in [('10.txt','utf-16'),('2.txt','cp1256'),('1.txt','utf-8-sig')]:
            p=self.root/name
            p.write_bytes('درس\r\nثان'.encode(encoding))
            paths.append(p)
        result=prepare(inputs=paths,work_dir=self.root/'prepared')
        m=read_json(result['manifest_path'])
        self.assertEqual([s['original_name'] for s in m['sources']],['10.txt','2.txt','1.txt'])
        self.assertEqual(len({s['sha256'] for s in m['sources']}),1)
        self.assertEqual(len(m['sources']),3)
        with self.assertRaises(ValueError):
            prepare(inputs=paths,work_dir=self.root/'prepared')
        result=prepare(input_dir=self.root,work_dir=self.root/'natural')
        m=read_json(result['manifest_path'])
        self.assertEqual([s['original_name'] for s in m['sources']],['1.txt','2.txt','10.txt'])

    def test_word_navigation_text_and_targets(self):
        from build_lesson import build
        from check_lesson import content_texts, norm
        doc,_,_=compile_course(self.data,self.manifest)
        captured=[]
        with patch('build_lesson.materialize', side_effect=lambda d,*args: captured.append(d)):
            build(doc,self.root/'unused.docx',self.root/'unused-build')
        xml=captured[0].element
        ns={'w':'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
        texts=norm(' '.join(xml.xpath('//w:t/text()')))
        bookmarks=set(xml.xpath('//w:bookmarkStart/@w:name'))
        anchors=xml.xpath('//w:hyperlink/@w:anchor')
        self.assertEqual(len(anchors),6)
        self.assertTrue(set(anchors)<=bookmarks)
        for topic in doc['topics']:
            for block in topic['blocks']:
                if block['type']=='paragraph' and isinstance(block['text'],list) and any('anchor' in s for s in block['text']):
                    expected=norm(''.join(s['text'] for s in block['text']))
                    self.assertIn(expected,texts)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--work-dir',required=True,type=Path)
    args=p.parse_args()
    args.work_dir.mkdir(parents=True,exist_ok=True)
    WORK=args.work_dir.resolve()
    unittest.main(argv=['test_pipeline.py'],verbosity=2)
