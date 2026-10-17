"""Merge only contiguous fresh Word chunks, then render every page for inspection."""
import argparse,re
from pathlib import Path
import pymupdf as fitz
from common import write_json
def main():
    ap=argparse.ArgumentParser();ap.add_argument('chunks');ap.add_argument('outdir');ap.add_argument('--dpi',type=int,default=130);a=ap.parse_args()
    out=Path(a.outdir);out.mkdir(parents=True,exist_ok=True);parts=[]
    for p in Path(a.chunks).glob('pages-*.pdf'):
        m=re.fullmatch(r'pages-(\d+)-(\d+)\.pdf',p.name)
        if m:parts.append((int(m[1]),int(m[2]),p))
    parts.sort();nextpage=1;pdf=fitz.open()
    for start,end,path in parts:
        if start!=nextpage:raise ValueError('Missing/overlapping PDF chunk')
        with fitz.open(path) as part:
            if len(part)!=end-start+1:raise ValueError('Chunk page count mismatch')
            pdf.insert_pdf(part)
        nextpage=end+1
    if not parts:raise ValueError('No PDF chunks')
    pdf.save(out/'document.pdf',deflate=True);flags=[]
    for i,page in enumerate(pdf,1):
        page.get_pixmap(dpi=a.dpi,alpha=False).save(out/f'page-{i:03d}.png')
        # Automated out-of-page check is a supplement, never the visual shipping gate.
        spans=[s for b in page.get_text('dict')['blocks'] if 'lines' in b for l in b['lines'] for s in l['spans']]
        # Word can emit invisible header anchor whitespace outside the media box.
        # A blank glyph's font bounds are not clipped lesson content.
        outside=[s['text'] for s in spans if s['text'].strip() and (fitz.Rect(s['bbox']).x0<0 or fitz.Rect(s['bbox']).y0<0 or fitz.Rect(s['bbox']).x1>page.rect.width+1 or fitz.Rect(s['bbox']).y1>page.rect.height+1)]
        if outside:flags.append({'page':i,'outside':outside})
    write_json(out/'render-report.json',{'pages':len(pdf),'geometry_flags':flags,'visual_review':'pending'});pdf.close()
    print(f'{nextpage-1} pages rendered; inspect each PNG and record review evidence.')
if __name__=='__main__':main()
