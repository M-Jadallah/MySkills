"""Check actual assets/DOCX packages, not just plan intentions. Requires final visual evidence separately."""
import argparse,io,re
from pathlib import Path
from zipfile import ZipFile
from lxml import etree as E
from PIL import Image
from common import ROOT,NS,read_json,write_json,digest

def audit_assets():
    identity=read_json(ROOT/'assets/identity.json');errors=[]
    for item in identity['files']:
        p=ROOT/'assets'/item['path']
        if not p.exists() or digest(p)!=item['sha256']:errors.append('Asset changed/missing: '+item['path'])
        if p.exists() and item['path'].startswith('ribbons/'):
            im=Image.open(p)
            if im.mode!='RGBA' or im.getchannel('A').getextrema()[0]!=0:errors.append('Ribbon not truly transparent: '+item['path'])
    return {'status':'passed' if not errors else 'failed','errors':errors,'asset_count':len(identity['files'])}
def audit_docx(path,cards=None,final=False,expected_answer_areas=None):
    errors=[];warnings=[]
    with ZipFile(path) as z:
        bad=z.testzip()
        if bad:errors.append('Broken ZIP part '+bad)
        roots={n:E.fromstring(z.read(n),E.XMLParser(resolve_entities=False,no_network=True)) for n in z.namelist() if n.endswith('.xml')}
        root=roots['word/document.xml'];body=root.find('w:body',NS)
        headers=[v for k,v in roots.items() if re.search(r'word/header\d+\.xml$',k)]
        badges=[n for h in headers for n in h.findall('.//wp:docPr',NS) if n.get('name')=='AltayfUnitBadge']
        if not badges:errors.append('Editable unit badge missing beside lesson title')
        elif not any(re.search(r'الوحدة\s*[0-9]{1,2}', ''.join(h.itertext('{'+NS['w']+'}t'))) for h in headers):errors.append('Unit badge has no visible verified number')
        sect=root.find('.//w:sectPr',NS);size=sect.find('w:pgSz',NS)
        if abs(int(size.get('{'+NS['w']+'}w'))-11906)>2 or abs(int(size.get('{'+NS['w']+'}h'))-16838)>2:errors.append('Approved A4 page geometry changed')
        for n in body.findall('.//w:shd',NS):
            if n.get('{'+NS['w']+'}fill','auto') not in ['auto','FFFFFF'] or n.get('{'+NS['w']+'}val') not in ['nil','clear',None]:errors.append('Opaque body cell/paragraph shading found')
            elif n.get('{'+NS['w']+'}fill')=='FFFFFF':errors.append('Opaque white shading hides page background')
        for n in body.findall('.//w:trHeight',NS):
            if n.get('{'+NS['w']+'}hRule')=='exact':errors.append('Fixed row height risks clipping')
        named_tables={}
        for table in body.findall('.//w:tbl',NS):
            cap=table.find('w:tblPr/w:tblCaption',NS)
            if cap is None:continue
            name=cap.get('{'+NS['w']+'}val','');named_tables[name]=named_tables.get(name,0)+1
            if name=='AltayfDataTable':
                for run in table.findall('.//w:r',NS):
                    if not ''.join(run.itertext('{'+NS['w']+'}t')).strip():continue
                    sz=run.find('w:rPr/w:szCs',NS)
                    if sz is None or sz.get('{'+NS['w']+'}val')!='21':errors.append('Data table run is not 10.5 pt')
            if name=='AltayfGlossary':
                ps=table.findall('.//w:tc/w:p',NS)
                if len(ps)<2:errors.append('Glossary card lacks separate term and definition lines')
                elif not ps[0].findall('.//w:bCs',NS):errors.append('Glossary term is not bold')
        if expected_answer_areas is not None and named_tables.get('AltayfAnswerArea',0)!=expected_answer_areas:
            errors.append(f'Answer-area mismatch: expected {expected_answer_areas}, found {named_tables.get("AltayfAnswerArea",0)}')
        text=''.join(root.itertext('{'+NS['w']+'}t'))
        if "{'text':" in text or '{"text":' in text:errors.append('Serialized rich-text object leaked into visible document')
        if '{{LESSON_TITLE}}' in ''.join(''.join(r.itertext()) for r in roots.values()):errors.append('Unfilled lesson title slot')
        if re.search(r'(?:شكل|رسم)\s*[（(]?\s*\d+',text):warnings.append('Possible numbered figure scaffold; inspect and remove only label, not scientific values')
        background=digest(ROOT/'assets/page/background.png')
        media={n:z.read(n) for n in z.namelist() if n.startswith('word/media/')}
        from hashlib import sha256
        if background not in {sha256(b).hexdigest() for b in media.values()}:errors.append('Approved background pixels missing')
        for name,blob in media.items():
            try:im=Image.open(io.BytesIO(blob))
            except Exception:continue
            if sha256(blob).hexdigest()==background:continue
            if im.mode!='RGBA' or im.getchannel('A').getextrema()[0]!=0:warnings.append('Media may have a rectangular mat; visually check '+name)
        maths=[n for n in root.iter() if n.tag=='{'+NS['m']+'}oMath']
        alphas=root.findall('.//a:alpha',NS)
        named=root.findall('.//wp:docPr',NS)
        fills=[n for n in named if n.get('name','').startswith('AltayfCard') and n.get('name','').endswith('_transparent_background')]
        if final and cards is not None:
            expected={r['name']+'_transparent_background' for r in read_json(cards)}
            actual={n.get('name') for n in fills}
            if actual!=expected:errors.append('Missing/extra named tint shapes: '+str(sorted(actual^expected)))
            for n in fills:
                anchor=n.getparent();aa=anchor.findall('.//a:alpha',NS)
                if not aa or any(x.get('val')!='6000' for x in aa):errors.append('Card alpha differs from 6 percent opacity '+n.get('name'))
        if 'تذكّر عند الحل' not in text:errors.append('Closing تذكّر عند الحل section missing')
    return {'status':'passed' if not errors else 'failed','errors':errors,'warnings':warnings,'equations':len(maths),'tint_shapes':len(fills),'media':len(media),'styled_tables':named_tables,'visual_review':'required separately'}
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--assets',action='store_true');ap.add_argument('--docx');ap.add_argument('--cards');ap.add_argument('--final',action='store_true');ap.add_argument('--expected-answer-areas',type=int);ap.add_argument('--report',required=True);a=ap.parse_args()
    report=audit_assets() if a.assets else audit_docx(a.docx,a.cards,a.final,a.expected_answer_areas)
    write_json(a.report,report);print(report['status'],len(report['errors']),'errors',len(report.get('warnings',[])),'warnings')
    for e in report['errors']:print(e)
    raise SystemExit(1 if report['errors'] else 0)
if __name__=='__main__':main()
