"""Template-preserving DOCX generation, rendering and verification helpers."""
from __future__ import annotations
import collections
import concurrent.futures
import copy
import hashlib
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
import unicodedata
import zipfile

import openpyxl
import pdfplumber
from lxml import etree as E
from PIL import Image,ImageDraw,ImageFont
from pypdf import PdfReader

from core import SKILL
from inputs import write
from planner import PlanError

W={'w':'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
S={'s':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
ST='{'+S['s']+'}'


def patch_workbook(path,job,grouped=False):
    tmp=path.with_suffix('.native.tmp')
    with zipfile.ZipFile(SKILL/'assets/plan-template.xlsx') as original:
        original_cols=E.fromstring(original.read('xl/worksheets/sheet1.xml')).find('s:cols',S)
    with zipfile.ZipFile(path) as source,zipfile.ZipFile(tmp,'w',zipfile.ZIP_DEFLATED) as out:
        for entry in source.infolist():
            content=source.read(entry.filename)
            match=re.fullmatch(r'xl/worksheets/sheet(\d+)\.xml',entry.filename)
            if match:
                index=int(match[1])-2
                root=E.fromstring(content)
                view=root.find('s:sheetViews/s:sheetView',S)
                view.set('rightToLeft','1');view.set('tabSelected','1' if index==-1 else '0')
                if index>=0:
                    student=job['students'][index];compact=grouped and not student['unchanged']
                    rows=student['grouped_rows'] if grouped else student['rows']
                    cols=root.find('s:cols',S)
                    if not compact:
                        position=list(root).index(cols);root.remove(cols);root.insert(position,copy.deepcopy(original_cols))
                    else:
                        for col in cols:
                            start,end=int(col.get('min')),int(col.get('max'))
                            if start==end==3:col.set('width','112')
                            if start==end==5:col.set('width','16')
                            if start==end==4 or start>=6:col.set('hidden','1')
                    data=root.find('s:sheetData',S)
                    for row in list(data):
                        if int(row.get('r'))>len(rows)+1:
                            if any(c.find('s:v',S) is not None or c.find('s:is',S) is not None or c.find('s:f',S) is not None for c in row):raise PlanError('trailing_data')
                            data.remove(row)
                        elif row.get('r')!='1':
                            for cell in list(row):
                                if re.fullmatch(r'A\d+',cell.get('r','')):
                                    if any(cell.find('s:'+tag,S) is not None for tag in ('v','f','is')):raise PlanError('id_not_empty')
                                    row.remove(cell)
                    dim=root.find('s:dimension',S)
                    if dim is not None:dim.set('ref',f'A1:K{len(rows)+1}')
                content=E.tostring(root,encoding='UTF-8',xml_declaration=True,standalone=True)
            out.writestr(entry,content)
    os.replace(tmp,path)
    sidecar=path.with_name(path.name+'.inspect.ndjson')
    if sidecar.exists():sidecar.replace(pathlib.Path(job['work_dir'])/('export-grouped.ndjson' if grouped else 'export-detailed.ndjson'))


def verify_books(job):
    reports=[]
    for grouped,key in [(False,'detailed_path'),(True,'grouped_path')]:
        book=openpyxl.load_workbook(job[key],read_only=False,data_only=False)
        cached=openpyxl.load_workbook(job[key],read_only=True,data_only=True)
        assert book.sheetnames==['الإحصائيات']+[s['sheet_name'] for s in job['students']]
        for i,student in enumerate(job['students']):
            expected=student['grouped_rows'] if grouped else student['rows']
            sheet=book[student['sheet_name']]
            actual=[list(r) for r in sheet.iter_rows(min_row=2,max_col=11,values_only=True) if r[1] is not None]
            assert actual==expected,(student['name'],'export_rows')
            assert all(row[0] is None and row[1]==n for n,row in enumerate(actual,1))
            assert sheet.sheet_view.rightToLeft
            assert sheet.max_column==11
            if not grouped or student['unchanged']:
                assert [c.value for c in sheet[1]]==job['headers']
                assert {k:d.width for k,d in sheet.column_dimensions.items()}==job['column_widths']
            assert sum(row[4] for row in actual)==student['total_weight']
            sr=i+7
            values=[cached.worksheets[0].cell(sr,col).value for col in range(3,10 if grouped else 8)]
            controls=[len(student['rows']),student['medium_weight'],student['weak_weight'],student['total_weight'],student['total_weight']/6]+([student['daily_weight'],len(expected)] if grouped else [])
            assert all(isinstance(a,(int,float)) and abs(a-b)<1e-8 for a,b in zip(values,controls))
        assert not [(s.title,c.coordinate) for s in book for row in s for c in row if c.data_type=='e']
        total=7+len(job['students'])
        assert cached.worksheets[0].cell(total,6).value==sum(s['total_weight'] for s in job['students'])
        reports.append({'path':job[key],'verified':True,'id_empty':True,'students':len(job['students'])})
        book.close();cached.close()
    # Prove short plan cells/styles/widths/heights are identical across both files.
    a=openpyxl.load_workbook(job['detailed_path']);b=openpyxl.load_workbook(job['grouped_path'])
    for s in job['students']:
        if not s['unchanged']:continue
        x,y=a[s['sheet_name']],b[s['sheet_name']]
        assert x.max_row==y.max_row
        for rx,ry in zip(x,y):
            for cx,cy in zip(rx,ry):
                assert cx.value==cy.value and copy.copy(cx.font)==copy.copy(cy.font) and copy.copy(cx.fill)==copy.copy(cy.fill) and copy.copy(cx.alignment)==copy.copy(cy.alignment) and cx.number_format==cy.number_format
        assert {k:v.height for k,v in x.row_dimensions.items()}=={k:v.height for k,v in y.row_dimensions.items()}
    a.close();b.close()
    return reports


def requirement_nodes(root):
    rows=root.find('w:body/w:tbl',W).findall('w:tr',W)
    assert len(rows)==9
    return [r.findall('w:tc',W)[2].findall('w:p/w:r/w:t',W) for r in rows[1:]]


def build_docs(job):
    template=SKILL/'assets/student-template.docx'
    assert hashlib.sha256(template.read_bytes()).hexdigest()=='31a2fc12695e77eed6d381d2674ea94fa36992e32df4f0dc71a38b9b1adfdd43'
    with zipfile.ZipFile(template) as archive:
        parts={n:archive.read(n) for n in archive.namelist()};infos=archive.infolist()
    actual=openpyxl.load_workbook(job['grouped_path'],read_only=True,data_only=True)
    for student in job['students']:
        rows=[list(r) for r in actual[student['sheet_name']].iter_rows(min_row=2,values_only=True) if r[1] is not None]
        assert rows==student['grouped_rows']
        labels=[str(r[2]) for r in rows]
        root=E.fromstring(parts['word/document.xml']);header=E.fromstring(parts['word/header1.xml'])
        for number,(nodes,text) in enumerate(zip(requirement_nodes(root),labels+['']*(8-len(labels))),1):
            assert ''.join(n.text or '' for n in nodes)==f'المطلوب {number}'
            nodes[0].text=text
            for n in nodes[1:]:n.text=''
        node=header.findall('w:p',W)[1].find('w:r/w:t',W)
        assert node.text=='( الطالب';node.text=f'( {student["name"]}'
        replacements={'word/document.xml':E.tostring(root,encoding='UTF-8',xml_declaration=True,standalone=True),'word/header1.xml':E.tostring(header,encoding='UTF-8',xml_declaration=True,standalone=True)}
        path=pathlib.Path(job['output_dir'])/'Word'/f'{student["file_stem"]}.docx'
        path.parent.mkdir(parents=True,exist_ok=True)
        with zipfile.ZipFile(path,'w',zipfile.ZIP_DEFLATED) as out:
            for info in infos:out.writestr(info,replacements.get(info.filename,parts[info.filename]))
        student['docx']=str(path);student['pdf']=str(pathlib.Path(job['output_dir'])/'PDF'/f'{student["file_stem"]}.pdf');student['labels']=labels
    actual.close()


def verify_docx(student):
    with zipfile.ZipFile(SKILL/'assets/student-template.docx') as ref,zipfile.ZipFile(student['docx']) as doc:
        assert doc.testzip() is None and doc.namelist()==ref.namelist()
        for n in ref.namelist():
            if n not in ('word/document.xml','word/header1.xml'):assert doc.read(n)==ref.read(n),(student['name'],n)
        root=E.fromstring(doc.read('word/document.xml'));base=E.fromstring(ref.read('word/document.xml'))
        slots=requirement_nodes(root);originals=requirement_nodes(base)
        assert [''.join(n.text or '' for n in group) for group in slots]==student['labels']+['']*(8-len(student['labels']))
        for nodes,old in zip(slots,originals):
            for a,b in zip(nodes,old):a.text=b.text
        assert E.tostring(root,method='c14n')==E.tostring(base,method='c14n')
        header=E.fromstring(doc.read('word/header1.xml'));node=header.findall('w:p',W)[1].find('w:r/w:t',W)
        assert ''.join(header.findall('w:p',W)[1].xpath('.//w:t/text()',namespaces=W))==f'( {student["name"]} )'
        node.text='( الطالب'
        assert E.tostring(header,method='c14n')==E.tostring(E.fromstring(ref.read('word/header1.xml')),method='c14n')


def render_documents(job,renderer,soffice=None):
    work=pathlib.Path(job['work_dir']);renderer=pathlib.Path(renderer).resolve()
    if not renderer.is_file():raise PlanError('renderer_missing')
    def run(student):
        directory=work/'renders'/f'{student["index"]:03d}';directory.mkdir(parents=True,exist_ok=True)
        env=dict(os.environ)
        if soffice:env['PATH']=str(pathlib.Path(soffice).resolve().parent)+os.pathsep+env.get('PATH','')
        output=subprocess.run([sys.executable,str(renderer),student['docx'],'--output_dir',str(directory),'--emit_pdf'],env=env,capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=180)
        (directory/'render.log').write_text(output.stdout+output.stderr,encoding='utf-8')
        pdf=directory/(pathlib.Path(student['docx']).stem+'.pdf')
        if output.returncode or not pdf.exists():raise PlanError(f'docx_render_failed:{student["name"]}:{output.stderr or output.stdout}')
        if len(PdfReader(pdf).pages)!=1:raise PlanError(f'template_overflow:{student["name"]}: لا تحذف محتوى أو تصغّر الخط صمتًا')
        target=pathlib.Path(student['pdf']);target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(pdf,target)
        return {'name':student['name'],'path':str(directory/'page-1.png'),'pdf':str(target)}
    results=[]
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        for future in concurrent.futures.as_completed([pool.submit(run,s) for s in job['students']]):
            results.append(future.result());print(f'DOCX/PDF {len(results)}/{len(job["students"])}',flush=True)
    write(work/'document-previews.json',{'preview_complete':True,'results':results})


def text_chars(text):
    return collections.Counter(c for c in unicodedata.normalize('NFKC',text) if c.isalpha() or c.isdigit() or c=='+')


def visible_text(page):return ''.join(c['text'] for c in page.chars if c['x1']-c['x0']>.01)


def verify_pdf(student):
    with zipfile.ZipFile(student['docx']) as doc:
        expected=' '.join(' '.join(E.fromstring(doc.read(part)).xpath('.//w:t/text()',namespaces=W)) for part in ['word/document.xml','word/header1.xml'])
    with pdfplumber.open(student['pdf']) as pdf:
        assert len(pdf.pages)==1
        p=pdf.pages[0]
        assert abs(p.width-595.3)<1 and abs(p.height-841.9)<1
        assert text_chars(visible_text(p))==text_chars(expected),(student['name'],'pdf_text')
        tables=p.find_tables();assert len(tables)==1 and len(tables[0].rows)==9 and len(tables[0].cells)==27
        table=tables[0];assert abs(table.bbox[0]-66.1)<1 and abs(table.bbox[1]-117.86)<1 and table.bbox[3]<p.height-55
        for i,row in enumerate(table.rows[1:]):
            box=row.cells[0];crop=p.crop(box);label=student['labels'][i] if i<len(student['labels']) else ''
            assert text_chars(visible_text(crop))==text_chars(label),(student['name'],i,'pdf_cell_text')
            assert all(c['top']>=box[1]-.5 and c['bottom']<=box[3]+.5 for c in crop.chars if c['text'].strip())
    return {'name':student['name'],'pages':1,'requirements':len(student['labels']),'verified':True}


def package(job,report):
    if not report.get('verified'):raise PlanError('verification_required')
    output=pathlib.Path(job['output_dir']);target=output/'حزمة خطط التثبيت.zip'
    with zipfile.ZipFile(target,'w',zipfile.ZIP_DEFLATED) as out:
        for key in ['detailed_path','grouped_path']:
            path=pathlib.Path(job[key]);out.write(path,path.name)
        for s in job['students']:
            for kind in ['docx','pdf']:
                path=pathlib.Path(s[kind]);out.write(path,('Word/' if kind=='docx' else 'PDF/')+path.name)
    with zipfile.ZipFile(target) as archive:
        assert archive.testzip() is None and len(archive.namelist())==2+2*len(job['students'])
    return str(target)
