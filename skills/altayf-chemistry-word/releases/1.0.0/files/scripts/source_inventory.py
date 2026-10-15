"""Read-only OOXML inventory. Does not execute macros, source instructions or external links."""
import argparse, posixpath
from pathlib import Path
from zipfile import ZipFile
from hashlib import sha256
from lxml import etree as E
from common import NS, digest, write_json

def inside_fallback(n):return any(a.tag=='{'+NS['mc']+'}Fallback' for a in n.iterancestors())
def main():
    ap=argparse.ArgumentParser();ap.add_argument('source');ap.add_argument('outdir');a=ap.parse_args()
    src=Path(a.source).resolve();out=Path(a.outdir).resolve();out.mkdir(parents=True,exist_ok=True)
    manifest={'source':str(src),'sha256':digest(src),'paragraphs':[],'tables':[],
              'equations':[],'media':[],'objects':[],'relationships':[],'review_flags':[]}
    parser=E.XMLParser(resolve_entities=False,no_network=True)
    with ZipFile(src) as z:
        xmlnames=[n for n in z.namelist() if n.startswith('word/') and n.endswith('.xml')]
        for name in xmlnames:
            if not (name=='word/document.xml' or any(x in name for x in ['header','footer','footnotes','endnotes','comments','charts/','diagrams/'])):continue
            root=E.fromstring(z.read(name),parser);short=name.removeprefix('word/').removesuffix('.xml').replace('/','_')
            if any(x in name for x in ['charts/','diagrams/']):
                path=out/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(z.read(name))
                manifest['objects'].append({'id':'O-'+short,'part':name,'file':name,'text_values':[n.text for n in root.iter() if n.text and n.text.strip()], 'sha256':digest(path)})
                manifest['review_flags'].append({'part':name,'kind':'chart_or_smartart','action':'Read scientific labels, values, units and arrangement visually and preserve their facts; XML extraction alone is not sufficient.'})
            for i,n in enumerate(root.findall('.//a:txBody',NS),1):
                if not inside_fallback(n):
                    manifest['objects'].append({'id':f'O-{short}-DrawingText{i:04d}','part':name,'xpath':root.getroottree().getpath(n),'text_values':[t.text for t in n.findall('.//a:t',NS) if t.text]})
            for i,p in enumerate(root.findall('.//w:p',NS),1):
                if inside_fallback(p):continue
                # Exclude nested text-box paragraphs from host text; inventory them separately.
                texts=[n.text or '' for n in p.findall('.//w:t',NS) if not inside_fallback(n) and next(n.iterancestors('{'+NS['w']+'}p')) is p]
                maths=p.findall('./m:oMath',NS)+p.findall('./m:oMathPara',NS)
                images=p.findall('.//a:blip',NS)
                if texts or maths or images:
                    runs=[]
                    for r in p.findall('./w:r',NS):
                        rt=''.join(x.text or '' for x in r.findall('./w:t',NS))
                        if not rt:continue
                        rp=r.find('w:rPr',NS)
                        bn=rp.find('w:bCs',NS) if rp is not None else None
                        if bn is None and rp is not None:bn=rp.find('w:b',NS)
                        cn=rp.find('w:color',NS) if rp is not None else None
                        runs.append({'text':rt,'bold_direct':bn is not None and bn.get('{'+NS['w']+'}val','1') not in ['0','false'],
                                     'color_direct':cn.get('{'+NS['w']+'}val') if cn is not None else None})
                    manifest['paragraphs'].append({'id':f'S-{short}-P{i:04d}','part':name,'xpath':root.getroottree().getpath(p),'text':''.join(texts),
                         'runs':runs,
                         'style':p.find('w:pPr/w:pStyle',NS).get('{'+NS['w']+'}val') if p.find('w:pPr/w:pStyle',NS) is not None else None,
                         'table_depth':sum(t.tag=='{'+NS['w']+'}tbl' for t in p.iterancestors()),
                         'textbox':any(t.tag=='{'+NS['w']+'}txbxContent' for t in p.iterancestors())})
            for i,t in enumerate(root.findall('.//w:tbl',NS),1):
                if inside_fallback(t):continue
                rows=[]
                for tr in t.findall('w:tr',NS):
                    rows.append(['\n'.join(''.join(p.itertext('{'+NS['w']+'}t')) for p in c.findall('./w:p',NS)) for c in tr.findall('w:tc',NS)])
                manifest['tables'].append({'id':f'S-{short}-T{i:04d}','part':name,'xpath':root.getroottree().getpath(t),'rows':rows,
                                          'nested':any(t2.tag==t.tag for t2 in t.iterancestors())})
            # Store one root per equation, not both oMathPara and its child oMath.
            eq=[n for n in root.iter() if n.tag in ['{'+NS['m']+'}oMath','{'+NS['m']+'}oMathPara'] and not any(p.tag=='{'+NS['m']+'}oMathPara' for p in n.iterancestors()) and not inside_fallback(n)]
            for i,n in enumerate(eq,1):
                eid=f'M-{short}-{i:04d}';path=out/'equations'/f'{eid}.xml';path.parent.mkdir(exist_ok=True)
                path.write_bytes(E.tostring(n,xml_declaration=True,encoding='UTF-8'))
                manifest['equations'].append({'id':eid,'part':name,'xpath':root.getroottree().getpath(n),'file':str(path.relative_to(out)),
                    'text':''.join(n.itertext('{'+NS['m']+'}t')),'sha256':digest(path)})
            if root.findall('.//w:altChunk',NS):manifest['review_flags'].append({'part':name,'kind':'altChunk','action':'Extract embedded content before coverage approval.'})
            if root.findall('.//w:del',NS) or root.findall('.//w:ins',NS):manifest['review_flags'].append({'part':name,'kind':'tracked_changes','action':'Resolve intended revision with user context; do not silently accept/delete.'})
            if root.findall('.//w:object',NS):manifest['review_flags'].append({'part':name,'kind':'embedded_object','action':'Inspect the embedded scientific object, not only preview text.'})
        for name in z.namelist():
            if name.startswith('word/media/') or name.startswith('word/embeddings/'):
                path=out/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(z.read(name))
                manifest['media'].append({'id':name,'file':name,'sha256':digest(path),'bytes':path.stat().st_size})
            if name.endswith('.rels'):
                root=E.fromstring(z.read(name),parser)
                for r in root:
                    manifest['relationships'].append({'part':name,**dict(r.attrib)})
                    if r.get('TargetMode')=='External':manifest['review_flags'].append({'part':name,'kind':'external_relationship','target':r.get('Target'),'action':'Do not fetch/execute automatically. Determine whether necessary source content is missing.'})
    write_json(out/'inventory.json',manifest)
    print(f"Inventoried {len(manifest['paragraphs'])} paragraphs, {len(manifest['tables'])} tables, {len(manifest['equations'])} equations, {len(manifest['media'])} media; {len(manifest['review_flags'])} review flags.")
if __name__=='__main__':main()

