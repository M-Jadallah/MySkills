"""Use the documents skill's canonical PNG renderer after a native Word export."""
import argparse
import importlib.util
import os
import shutil
import sys
from pathlib import Path

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('document',type=Path)
    parser.add_argument('--pdf',type=Path,required=True)
    parser.add_argument('--renderer',type=Path,required=True,help='Current documents-skill render_docx.py')
    parser.add_argument('--output-dir',type=Path,required=True)
    parser.add_argument('--dpi',type=int,default=120)
    parser.add_argument('--poppler-bin',type=Path)
    args=parser.parse_args()
    for p in [args.document,args.pdf,args.renderer]:
        if not p.is_file():parser.error(f'Missing input: {p}')
    native_poppler=Path(sys.executable).parent.parent/'native'/'poppler'/'Library'/'bin'
    poppler=args.poppler_bin or (native_poppler if native_poppler.is_dir() else None)
    if poppler:os.environ['PATH']=str(poppler)+os.pathsep+os.environ.get('PATH','')
    spec=importlib.util.spec_from_file_location('course_render_docx',args.renderer)
    renderer=importlib.util.module_from_spec(spec);spec.loader.exec_module(renderer)
    pdf_source=args.pdf.resolve()
    def exported_pdf(document,user_profile,output_dir,stem,verbose=False):
        target=Path(output_dir)/(stem+'.pdf')
        shutil.copy2(pdf_source,target)
        return str(target),'Microsoft Word native export'
    renderer.convert_to_pdf=exported_pdf
    sys.argv=[str(args.renderer),str(args.document),'--output_dir',str(args.output_dir),'--dpi',str(args.dpi)]
    renderer.main()

if __name__=='__main__':main()
