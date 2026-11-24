"""CLI entry point. Asset paths are relative; runtimes come from the loader."""
from __future__ import annotations
import argparse
import base64
import hashlib
import json
import os
import pathlib
import shutil
import subprocess
import sys

import openpyxl

from core import CATALOG,SKILL,group_rows,partition
from deliverables import build_docs,package,patch_workbook,render_documents,verify_books,verify_docx,verify_pdf
from inputs import analyze,assess,load_request,sha,write
from planner import PlanError


def subprocess_receipt(command,receipt,log):
    if receipt.exists():receipt.unlink()
    result=subprocess.run([str(c) for c in command],capture_output=True,text=True,encoding='utf-8',errors='replace')
    log.write_text(result.stdout+result.stderr,encoding='utf-8')
    if not receipt.exists() or not json.loads(receipt.read_text(encoding='utf-8')).get('export_complete'):
        raise PlanError(f'export_failed:{result.returncode}:{result.stderr or result.stdout}')


def module_link(work,modules):
    link=work/'node_modules';modules=pathlib.Path(modules).resolve()
    if not modules.is_dir():raise PlanError('node_modules_missing')
    if link.exists():
        if link.resolve()!=modules:raise PlanError('node_modules_target_changed')
        return
    if os.name=='nt':
        # Native PowerShell junction, no shell-composed file operations.
        quote=lambda p:"'"+str(p).replace("'","''")+"'"
        script=f'New-Item -ItemType Junction -Path {quote(link)} -Target {quote(modules)} | Out-Null'
        encoded=base64.b64encode(script.encode('utf-16le')).decode('ascii')
        run=subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-EncodedCommand',encoded],capture_output=True,text=True,creationflags=subprocess.CREATE_NO_WINDOW)
        if run.returncode:raise PlanError(f'junction_failed:{run.stderr}')
    else:link.symlink_to(modules,target_is_directory=True)


def make_job(spec_path,work,output):
    request=load_request(spec_path)
    assessment=assess(request)
    if not assessment['ready']:
        write(work/'analysis.json',{k:v for k,v in assessment.items() if k!='students'})
        raise PlanError('unresolved_input: راجع analysis.json قبل التأليف')
    students=assessment['students']
    for index,student in enumerate(students,1):student['index']=index
    original=openpyxl.load_workbook(SKILL/'assets/plan-template.xlsx')
    widths={k:d.width for k,d in original.active.column_dimensions.items()};original.close()
    return {'version':1,'request_path':str(pathlib.Path(spec_path).resolve()),'request_sha256':sha(spec_path),'source':request['source'],'settings':request['settings'],'students':students,'headers':CATALOG['headers'],'column_widths':widths,'work_dir':str(work),'output_dir':str(output),'detailed_path':str(output/'خطط التثبيت التفصيلية والإحصائيات.xlsx'),'grouped_path':str(output/'خطط التثبيت المجمعة - ٨ عناصر.xlsx'),'asset_hashes':{p.name:sha(p) for p in (SKILL/'assets').iterdir() if p.is_file()}}


def build(args):
    work=pathlib.Path(args.work_dir).resolve();output=pathlib.Path(args.out_dir).resolve()
    work.mkdir(parents=True,exist_ok=True)
    if work==output:raise PlanError('separate_work_and_output_directories')
    if (work/'job.json').exists():raise PlanError('work_job_exists: استعمل resume أو مجلد عمل جديدًا')
    if output.exists() and any(output.iterdir()):raise PlanError('output_exists: استخدم مجلد إخراج جديدًا؛ الأصول لا تُستبدل')
    job=make_job(args.spec,work,output)
    output.mkdir(parents=True,exist_ok=True)
    job['runtime']={'node':args.node,'node_modules':args.node_modules,'renderer':args.renderer,'soffice':args.soffice}
    write(work/'job.json',job)
    continue_build(job,args)


def continue_build(job,args):
    work=pathlib.Path(job['work_dir']);output=pathlib.Path(job['output_dir'])
    node=pathlib.Path(args.node).resolve()
    if not node.is_file():raise PlanError('node_missing')
    module_link(work,args.node_modules)
    renderer=work/'workbooks.mjs';shutil.copyfile(SKILL/'scripts/workbooks.mjs',renderer)
    job_path=work/'job.json';write(job_path,job)
    if not (work/'workbook-verification.json').exists():
        if not all(pathlib.Path(job[key]).is_file() for key in ['detailed_path','grouped_path']):
            subprocess_receipt([node,renderer,job_path],work/'export-grouped.json',work/'workbooks.log')
        for grouped,key in [(False,'detailed_path'),(True,'grouped_path')]:patch_workbook(pathlib.Path(job[key]),job,grouped)
    report=verify_books(job);write(work/'workbook-verification.json',report)
    # Windows rendering can exit nonzero only after valid image receipts are
    # written. Verify both receipts and every PNG rather than ignoring failure.
    for kind in ['detailed','grouped']:(work/f'preview-{kind}.json').unlink(missing_ok=True)
    preview=subprocess.run([str(node),str(renderer),str(job_path),'preview'],capture_output=True,text=True,encoding='utf-8',errors='replace')
    (work/'preview.log').write_text(preview.stdout+preview.stderr,encoding='utf-8')
    for kind in ['detailed','grouped']:
        path=work/f'preview-{kind}.json'
        if not path.exists():raise PlanError(f'preview_failed:{kind}:{preview.stderr}')
        receipt=json.loads(path.read_text(encoding='utf-8'))
        if not receipt.get('preview_complete') or any(not pathlib.Path(x['path']).read_bytes().startswith(b'\x89PNG') for x in receipt['results']):raise PlanError('preview_invalid')
    build_docs(job);write(job_path,job)
    for student in job['students']:verify_docx(student)
    if not args.renderer:
        print(json.dumps({'built':True,'job':str(job_path),'render_pending':True,'students':len(job['students'])},ensure_ascii=False));return
    render_documents(job,args.renderer,args.soffice)
    report=verify(job_path)
    print(json.dumps({k:v for k,v in report.items() if k!='checks'},ensure_ascii=False))


def resume(args):
    path=pathlib.Path(args.job).resolve();job=json.loads(path.read_text(encoding='utf-8'))
    if sha(job['request_path'])!=job['request_sha256'] or sha(job['source']['path'])!=job['source']['sha256']:raise PlanError('resume_input_changed')
    if any(sha(SKILL/'assets'/name)!=digest for name,digest in job['asset_hashes'].items()):raise PlanError('resume_assets_changed')
    if pathlib.Path(job['work_dir']).resolve()!=path.parent:raise PlanError('resume_job_location_changed')
    output=pathlib.Path(job['output_dir']).resolve()
    for key in ['detailed_path','grouped_path']:
        if pathlib.Path(job[key]).resolve().parent!=output:raise PlanError('resume_output_path_escape')
    validate_job_plan(job)
    continue_build(job,args)


def validate_job_plan(job):
    request=load_request(job['request_path']);assessment=assess(request)
    if not assessment['ready']:raise PlanError('job_request_no_longer_ready')
    expected=assessment['students']
    if len(expected)!=len(job['students']):raise PlanError('job_student_count_changed')
    for a,b in zip(expected,job['students']):
        for key in ['name','sheet_name','file_stem','rows','grouped_rows','groups','total_weight','medium_weight','weak_weight','source_record']:
            if a[key]!=b[key]:raise PlanError(f'job_plan_changed:{a["name"]}:{key}')


def verify(job_path):
    path=pathlib.Path(job_path);job=json.loads(path.read_text(encoding='utf-8'))
    assert sha(job['source']['path'])==job['source']['sha256']
    assert sha(job['request_path'])==job['request_sha256']
    assert all(sha(SKILL/'assets'/name)==digest for name,digest in job['asset_hashes'].items())
    validate_job_plan(job)
    workbooks=verify_books(job)
    checks=[]
    for s in job['students']:
        assert group_rows(s['rows'])['grouped_rows']==s['grouped_rows']
        flat=[]
        for group in s['groups']:flat.extend(s['rows'][group['source_start']-2:group['source_end']-1])
        assert flat==s['rows']
        if len(s['rows'])<=8:assert s['grouped_rows']==s['rows']
        else:
            assert len(s['grouped_rows'])==8
            for g in s['groups'][:7]:
                assert g['weight']<=s['daily_weight'] or (s['allow_oversized_singletons'] and g['source_count']==1)
        assert sum(r[4] for r in s['grouped_rows'])==s['total_weight']
        verify_docx(s);checks.append(verify_pdf(s))
    report={'verified':True,'students':len(checks),'detailed_records':sum(len(s['rows']) for s in job['students']),'grouped_records':sum(len(s['grouped_rows']) for s in job['students']),'total_weight':sum(s['total_weight'] for s in job['students']),'unchanged_students':sum(s['unchanged'] for s in job['students']),'word_files':len(checks),'pdf_files':len(checks),'source_unchanged':True,'template_unchanged':True,'workbooks':workbooks,'checks':checks}
    write(path.parent/'verification.json',report)
    return report


def main():
    parser=argparse.ArgumentParser(description='مصنع خطط التثبيت: Excel ثم ثماني فترات ثم Word/PDF')
    sub=parser.add_subparsers(dest='command',required=True)
    a=sub.add_parser('analyze');a.add_argument('--input',required=True);a.add_argument('--work-dir',required=True);a.add_argument('--sheet');a.add_argument('--columns',help='JSON 1-based name/medium/weak columns');a.add_argument('--header-row',type=int)
    a=sub.add_parser('check');a.add_argument('--spec',required=True)
    a=sub.add_parser('build');a.add_argument('--spec',required=True);a.add_argument('--work-dir',required=True);a.add_argument('--out-dir',required=True);a.add_argument('--node',required=True);a.add_argument('--node-modules',required=True);a.add_argument('--renderer');a.add_argument('--soffice')
    a=sub.add_parser('resume');a.add_argument('--job',required=True);a.add_argument('--node',required=True);a.add_argument('--node-modules',required=True);a.add_argument('--renderer');a.add_argument('--soffice')
    for command in ['render','verify','package']:
        a=sub.add_parser(command);a.add_argument('--job',required=True)
        if command=='render':a.add_argument('--renderer',required=True);a.add_argument('--soffice')
        if command=='package':a.add_argument('--visual-reviewed',action='store_true',required=True)
    args=parser.parse_args()
    try:
        if args.command=='analyze':
            result=analyze(args.input,args.work_dir,args.sheet,json.loads(args.columns) if args.columns else None,args.header_row)
            print(json.dumps({k:v for k,v in result.items() if k!='students'},ensure_ascii=False))
        elif args.command=='check':
            request=load_request(args.spec);result=assess(request)
            print(json.dumps({'ready':result['ready'],'issues':result['issues'],'possible_duplicates':result['possible_duplicates'],'students':len(result['students']),'records':sum(len(s['rows']) for s in result['students']),'weights':sum(s['total_weight'] for s in result['students'])},ensure_ascii=False))
            return 0 if result['ready'] else 2
        elif args.command=='build':build(args)
        elif args.command=='resume':resume(args)
        elif args.command=='render':
            job=json.loads(pathlib.Path(args.job).read_text(encoding='utf-8'));validate_job_plan(job)
            if sha(job['request_path'])!=job['request_sha256'] or sha(job['source']['path'])!=job['source']['sha256']:raise PlanError('render_input_changed')
            render_documents(job,args.renderer,args.soffice);verify(args.job)
        elif args.command=='verify':print(json.dumps({k:v for k,v in verify(args.job).items() if k!='checks'},ensure_ascii=False))
        elif args.command=='package':
            job=json.loads(pathlib.Path(args.job).read_text(encoding='utf-8'));report=verify(args.job)
            report['visual_reviewed']=True;write(pathlib.Path(args.job).parent/'verification.json',report)
            print(json.dumps({'package':package(job,report)},ensure_ascii=False))
    except (PlanError,AssertionError,OSError,ValueError,KeyError) as error:
        print(json.dumps({'ok':False,'error':str(error) or type(error).__name__},ensure_ascii=False),file=sys.stderr);return 2
    return 0


if __name__=='__main__':raise SystemExit(main())
