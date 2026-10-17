"""Measure all marked card borders in Word's first PDF; restore approved border colors."""
import argparse
from zipfile import ZipFile, ZIP_DEFLATED
from pathlib import Path
from lxml import etree as E
import pymupdf as fitz
from common import NS, read_json, write_json
def main():
    ap=argparse.ArgumentParser();ap.add_argument('docx');ap.add_argument('pdf');ap.add_argument('cards');ap.add_argument('bounds');a=ap.parse_args()
    records=read_json(a.cards);colors={r['marker']:r for r in records};seen={};bounds=[]
    with fitz.open(a.pdf) as pdf:
        for num,page in enumerate(pdf,1):
            boxes={}
            for drawing in page.get_drawings():
                c=drawing['color'] or drawing['fill']
                if c:
                    rgb=''.join(f'{round(v*255):02X}' for v in c)
                    if rgb in colors:
                        box=fitz.Rect(drawing['rect']);boxes[rgb]=(boxes[rgb]|box) if rgb in boxes else box
            for marker,box in boxes.items():
                r=colors[marker];seen.setdefault(marker,[]).append(num);t=r['tint']
                bounds.append({'name':r['name'],'page':num,'left':box.x0,'top':box.y0,'width':box.width,'height':box.height,
                    'rgb':int(t[:2],16)+256*int(t[2:4],16)+65536*int(t[4:],16),'tint':t})
    missing=set(colors)-set(seen);split={colors[m]['name']:v for m,v in seen.items() if len(v)>1}
    if missing or split:raise ValueError(f'Geometry gate failed. Missing {missing}; split {split}. Reflow or explicitly split cards with fresh per-page anchors, then rerender. Never anchor every continuation fill to page one.')
    write_json(a.bounds,bounds)
    dest=Path(a.docx)
    with ZipFile(dest) as z:files={n:z.read(n) for n in z.namelist()}
    root=E.fromstring(files['word/document.xml'])
    for n in root.iter():
        c=n.get('{'+NS['w']+'}color')
        if c in colors:n.set('{'+NS['w']+'}color',colors[c]['border'])
    files['word/document.xml']=E.tostring(root,xml_declaration=True,encoding='UTF-8',standalone=True)
    temp=dest.with_suffix('.geometry-tmp.docx')
    with ZipFile(temp,'w',ZIP_DEFLATED) as z:
        for n,b in files.items():z.writestr(n,b)
    temp.replace(dest);print(f'{len(bounds)} measured card fills; borders restored.')
if __name__=='__main__':main()

