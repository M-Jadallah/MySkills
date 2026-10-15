"""Sequential native-Word layout pipeline. Produces QA evidence; does NOT approve visual quality."""
import argparse,subprocess,sys,shutil
from pathlib import Path
from common import ROOT,read_json,write_json,digest

def run(args):
    name=Path(args[args.index('-File')+1]).name if '-File' in args else (Path(args[1]).name if len(args)>1 else args[0])
    print('Running',name,flush=True)
    subprocess.run([str(x) for x in args],check=True)
def main():
    ap=argparse.ArgumentParser();ap.add_argument('manifest');ap.add_argument('qa_dir');a=ap.parse_args()
    manifest=Path(a.manifest).resolve();items=read_json(manifest);qa=Path(a.qa_dir).resolve()
    if qa.exists():raise ValueError('Use a new layout QA directory for each pass')
    qa.mkdir(parents=True);ps=shutil.which('pwsh') or shutil.which('pwsh.exe') or shutil.which('powershell.exe')
    if not ps:raise ValueError('Native Word pipeline needs Windows PowerShell. Use documented renderer fallback on other hosts.')
    def word(mode,doc,*extra):run([ps,'-NoProfile','-NonInteractive','-File',ROOT/'scripts/word_layout.ps1','-Mode',mode,'-DocumentPath',doc,*extra])
    for item in items:
        role=item['role'];path=Path(item['path']);cards=Path(item['cards']);job=qa/role
        print('ROLE',role,flush=True)
        word('export',path,'-OutputDirectory',job/'initial-chunks')
        run([sys.executable,ROOT/'scripts/render_pages.py',job/'initial-chunks',job/'initial-render'])
        run([sys.executable,ROOT/'scripts/card_geometry.py',path,job/'initial-render/document.pdf',cards,job/'bounds.json'])
        word('tint',path,'-BoundsPath',job/'bounds.json')
        word('export',path,'-OutputDirectory',job/'final-chunks')
        run([sys.executable,ROOT/'scripts/render_pages.py',job/'final-chunks',job/'final-render'])
        run([sys.executable,ROOT/'scripts/verify_ribbon_visibility.py',job/'final-render/document.pdf',job/'final-render',cards,'--report',job/'ribbon-visibility.json'])
        run([sys.executable,ROOT/'scripts/audit_package.py','--docx',path,'--cards',cards,'--final','--expected-answer-areas',item['answer_areas'],'--report',job/'package-audit.json'])
        item['sha256_final']=digest(path)
        item['pages']=read_json(job/'final-render/render-report.json')['pages']
        item['visual_review']='pending'
        # Persist progress after each successful file; later failures do not imply all five passed.
        write_json(manifest,items)
    print('Native layout and structural gates passed. Open and inspect every final PNG; visual approval is still pending.')
if __name__=='__main__':main()
