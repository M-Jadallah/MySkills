"""Check the final Word artifact against its authored course and rendered pages."""
import argparse
import json
import re
from pathlib import Path
from zipfile import ZipFile
from lxml import etree
from docx import Document
from docx.oxml.ns import qn
from validate_course import validate,bare,WORD_RE
import unicodedata

NS={'w':'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
def run_color(run,paragraph):
    return str(run.font.color.rgb or paragraph.style.font.color.rgb)

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('document',type=Path)
    parser.add_argument('--data',type=Path,required=True)
    parser.add_argument('--pages',type=Path,help='Word exporter JSON page report')
    parser.add_argument('--report',type=Path)
    args=parser.parse_args()
    data=json.loads(args.data.read_text(encoding='utf-8-sig'))
    result=validate(data);errors=list(result['errors'])
    doc=Document(args.document)
    body=[p.text for p in doc.paragraphs]
    expected=[]
    for unit in data['units']:
        if unit.get('basmala'):expected.append(unit['basmala'])
        for block in unit['blocks']:
            expected.append(' '.join(a['text']+' ﴿'+str(a['number']).translate(str.maketrans('0123456789','٠١٢٣٤٥٦٧٨٩'))+'﴾' for a in block['ayahs']))
            for para in block['paragraphs']:
                expected.append(''.join('﴿'+s['text']+'﴾' if s['kind']=='quran' else s['text'] for s in para['segments']))
    # Sequence comparison tolerates legitimate repeated phrases but catches
    # deletion, reordering and accidental content left in the template.
    actual=[p.text for p in doc.paragraphs if p.style.name=='Quran' or p._p.xpath('./w:bookmarkStart[starts-with(@w:name,"tafsir_")]')]
    if actual!=expected:errors.append('Quran/tafsir text sequence differs from the data')
    quran_runs=0
    for p in doc.paragraphs:
        tafsir=bool(p._p.xpath('./w:bookmarkStart[starts-with(@w:name,"tafsir_")]'))
        for r in p.runs:
            if not r.text:continue
            scripture=p.style.name=='Quran' or r.text.startswith('﴿')
            if scripture:
                quran_runs+=1
                if run_color(r,p)!='7A1F3D':errors.append('A Quran run is not burgundy')
                bold=r.font.bold if r.font.bold is not None else p.style.font.bold
                if not bold:errors.append('A Quran run is not bold')
            elif tafsir and run_color(r,p)!='000000':errors.append('A tafsir run is not black')
    with ZipFile(args.document) as z:
        texts=[]
        for name in z.namelist():
            if name.endswith('.xml'):
                root=etree.fromstring(z.read(name))
                if re.fullmatch(r'word/(document|header\d+|footer\d+)\.xml',name):
                    texts+=[''.join(p.xpath('.//w:t/text()',namespaces=NS)) for p in root.xpath('//w:p',namespaces=NS)]
        root=etree.fromstring(z.read('word/document.xml'))
        borders=root.xpath('//w:sectPr/w:pgBorders',namespaces=NS)
        if len(borders)!=len(doc.sections):errors.append('Missing section page border')
        for border in borders:
            if len(border)!=4 or any(e.get(qn('w:color'))!='154F42' for e in border):errors.append('Outer page border differs from the theme')
        headers=[n for n in z.namelist() if re.fullmatch(r'word/header\d+\.xml',n)]
        if not any('B89242' in z.read(n).decode().upper() for n in headers):errors.append('Missing inner gold frame')
    bad=[w for w in WORD_RE.findall(' '.join(texts)) if len(w)>1 and w!='هـ' and not any(unicodedata.category(c)=='Mn' for c in w)]
    if bad:errors.append('Final document has unvocalized words: '+repr(bad[:20]))
    if any('أَصْدَاءُ' in t or 'أصداء' in t for t in texts):errors.append('Superseded program name remains')
    if not any(data['program_name'] in t for t in texts):errors.append('Program name absent from headers/footer')
    total_blocks=sum(len(u['blocks']) for u in data['units'])
    if body.count('الْآيَاتُ الْكَرِيمَةُ')!=total_blocks or body.count('التَّفْسِيرُ')!=total_blocks:
        errors.append('Missing ayah/tafsir transition labels')
    pages=None
    if args.pages:
        page_data=json.loads(args.pages.read_text(encoding='utf-8-sig'))
        pages=page_data['pageInfo']
        expected_cover=re.sub(r'\s+',' ',data['cover_title']+' '+data['course_title']).strip()
        if re.sub(r'\s+',' ',pages[0]['text']).strip()!=expected_cover:
            errors.append('Cover must contain only the two requested titles')
        for question in data['questions']:
            matches=[p for p in pages if question['prompt'] in p['text']]
            if len(matches)!=1:errors.append(f'Question {question["id"]} missing/duplicated in rendered pages');continue
            if question['type']=='mcq' and not all(option in matches[0]['text'] for option in question['options']):
                errors.append(f'Question {question["id"]} and its options cross a page break')
        for p in pages[1:]:
            if len(bare(p['text']))<100:errors.append(f'Page {p["page"]} is nearly empty; inspect its page break')
    else:
        result['warnings'].append('No page report supplied; cover and page-break checks were not performed.')
    output={'ok':not errors,'errors':sorted(set(errors)),'warnings':result['warnings'],
            'pages':len(pages) if pages else None,'quran_runs':quran_runs,'questions':len(data['questions'])}
    text=json.dumps(output,ensure_ascii=False,indent=2)
    if args.report:args.report.write_text(text,encoding='utf-8')
    print(text);raise SystemExit(0 if output['ok'] else 1)

if __name__=='__main__':main()
