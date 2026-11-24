"""Read-only Excel input inventory and explicit row-resolution schema."""
from __future__ import annotations
import hashlib
import json
import pathlib
from collections import Counter

import openpyxl
from core import CATALOG, clean, parse_cell, safe_names, student_plan
from planner import PlanError,normalize

ALIASES={
    'name':{'اسم الطالب','اسم الطالب الثلاثي','الاسم','اسم الطالب الرباعي'},
    'medium':{'المتوسط','المتوسطة','متوسط','متوسطة'},
    'weak':{'الضعيف','الضعيفة','ضعيف','ضعيفة'},
}
DEFAULTS={'cumulative_pages':5,'allow_short_units':True,'periods':8,'weak_multiplier':2,'mixed_triple_tests':'omit','oversized_items':'singleton'}


def sha(path): return hashlib.sha256(pathlib.Path(path).read_bytes()).hexdigest()


def analyze(input_path,work,sheet_name=None,columns=None,header_row=None):
    source=pathlib.Path(input_path).resolve()
    book=openpyxl.load_workbook(source,read_only=True,data_only=False)
    candidates=[]
    for sheet in book:
        if sheet_name and sheet.title!=sheet_name: continue
        for row in sheet.iter_rows(min_row=1,max_row=min(sheet.max_row,20)):
            found={}
            for cell in row:
                for role,aliases in ALIASES.items():
                    if normalize(cell.value or '') in {normalize(x) for x in aliases}: found[role]=cell.column
            if columns:
                if set(columns)!={'name','medium','weak'} or len(set(columns.values()))!=3 or any(type(x)is not int or x<1 for x in columns.values()):raise PlanError('invalid_column_mapping')
                if max(columns.values())>sheet.max_column:continue
                if header_row is not None:
                    if row[0].row!=header_row:continue
                    found=columns
                else:
                    # Mapping selects columns, not a fictitious first-row header.
                    if not all(normalize(row[column-1].value or '') in {normalize(a) for a in ALIASES[role]} for role,column in columns.items()):continue
                    found=columns
            elif header_row is not None and row[0].row!=header_row:continue
            if len(found)==3:
                candidates.append((sheet.title,row[0].row,found)); break
    if len(candidates)!=1: raise PlanError(f'input_sheet_ambiguous:{[(s,r) for s,r,c in candidates]}: حدد الورقة/الأعمدة')
    title,header,cols=candidates[0]
    sheet=book[title]
    records=[]
    for row in sheet.iter_rows(min_row=header+1):
        cells={role:row[index-1] for role,index in cols.items()}
        raw={role:cell.value for role,cell in cells.items()}
        if all(v is None or clean(v)=='' for v in raw.values()): continue
        if any(cell.data_type=='f' for cell in cells.values()):
            raise PlanError(f'input_formula:{title}!{row[0].row}: يجب أن تكون المدخلات قيمًا نصية فعلية')
        record={'id':f'{title}:{row[0].row}','source_row':row[0].row,'raw':raw,'parsed':{},'parse_issues':[],'resolution':{}}
        for level in ['medium','weak']:
            try: record['parsed'][level]=parse_cell(raw[level])
            except PlanError as e:
                record['parsed'][level]=None
                record['parse_issues'].append({'level':level,'message':str(e)})
        records.append(record)
    book.close()
    request={'version':1,'source':{'path':str(source),'sha256':sha(source),'sheet':title,'header_row':header,'columns':cols},'settings':DEFAULTS,'records':records}
    path=pathlib.Path(work); path.mkdir(parents=True,exist_ok=True)
    request_path=path/'request.json'
    if request_path.exists(): raise PlanError('request_exists: لا تعِد الكتابة فوق قرارات محفوظة؛ استخدم مجلد عمل جديدًا')
    write(request_path,request)
    analysis=assess(request)
    write(path/'analysis.json',analysis)
    return {'request':str(request_path),'records':len(records),**analysis}


def write(path,value): pathlib.Path(path).write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')


def assess(request):
    problems=[]; students=[]; names={};seen=[];possible_duplicates=[]
    settings=request.get('settings',{})
    if settings.get('periods')!=8 or settings.get('weak_multiplier')!=2 or settings.get('mixed_triple_tests')!='omit' or settings.get('oversized_items')!='singleton':
        raise PlanError('unsupported_settings: هذه النسخة تثبت ثماني فترات وضعف الضعيف وحذف الثلاثية المختلطة')
    for record in request['records']:
        resolution=record.get('resolution',{})
        unknown=set(resolution)-{'skip','student_name','medium','weak','overlap_policy','reason'}
        if unknown: raise PlanError(f'unknown_resolution_keys:{record["id"]}:{sorted(unknown)}')
        if resolution and not resolution.get('reason'):
            problems.append({'record':record['id'],'message':'missing_resolution_reason'});continue
        if resolution.get('skip'):
            if not resolution.get('reason'): problems.append({'record':record['id'],'message':'missing_skip_reason'})
            continue
        name=clean(resolution.get('student_name',record['raw']['name']))
        if not name: problems.append({'record':record['id'],'message':'missing_student_name'}); continue
        if not isinstance(record['raw']['name'],str) and 'student_name' not in resolution:
            problems.append({'record':record['id'],'message':'invalid_student_name_type'}); continue
        key=normalize(name)
        if key in names:
            problems.append({'record':record['id'],'message':f'duplicate_name:{name}','other_record':names[key]}); continue
        names[key]=record['id']
        tokens=[normalize(t) for t in name.split()]
        for other_id,other_name,other_tokens in seen:
            small,large=sorted([tokens,other_tokens],key=len)
            cursor=iter(large)
            if len(small)>=3 and len(small)!=len(large) and all(any(x==token for x in cursor) for token in small):
                possible_duplicates.append({'records':[other_id,record['id']],'names':[other_name,name],'message':'تشابه اسم قصير وآخر أطول؛ راجع الهوية ولا تدمج آليًا'})
        seen.append((record['id'],name,tokens))
        segments={level:resolution.get(level,record['parsed'].get(level)) for level in ['medium','weak']}
        if any(v is None for v in segments.values()):
            problems.append({'record':record['id'],'name':name,'message':'unresolved_cell','details':record['parse_issues']}); continue
        if any(not isinstance(v,list) for v in segments.values()): raise PlanError('segments_must_be_lists')
        try:
            plan=student_plan(name,segments['medium'],segments['weak'],settings,resolution.get('overlap_policy','error'))
            plan['source_record']=record['id']; plan['source_raw']=record['raw']; plan['resolved_segments']=segments
            students.append(plan)
        except (PlanError,AssertionError) as e:
            problems.append({'record':record['id'],'name':name,'message':str(e) or 'planner_invariant_failed'})
    if not students and not problems: problems.append({'message':'no_students'})
    if not problems: safe_names(students)
    return {'ready':not problems,'issues':problems,'possible_duplicates':possible_duplicates,'students':students}


def load_request(path):
    request=json.loads(pathlib.Path(path).read_text(encoding='utf-8-sig'))
    if request.get('version')!=1: raise PlanError('request_version')
    source=request['source']
    if sha(source['path'])!=source['sha256']: raise PlanError('input_changed: أعد التحليل ولا تطبق قرارات على ملف مختلف')
    # Source rows cannot disappear by editing the review JSON. Decisions belong
    # only in resolution; raw text and parser proposals must retain their origin.
    book=openpyxl.load_workbook(source['path'],read_only=True,data_only=False)
    sheet=book[source['sheet']]
    actual={}
    for row in sheet.iter_rows(min_row=source['header_row']+1):
        raw={role:row[index-1].value for role,index in source['columns'].items()}
        if all(v is None or clean(v)=='' for v in raw.values()):continue
        actual[f'{sheet.title}:{row[0].row}']=raw
    records=request['records']
    if len(records)!=len(actual) or {r['id'] for r in records}!=set(actual):raise PlanError('source_rows_removed_or_duplicated')
    for record in records:
        if record['raw']!=actual[record['id']]:raise PlanError(f'source_raw_changed:{record["id"]}')
        for level in ['medium','weak']:
            try: parsed=parse_cell(record['raw'][level])
            except PlanError:parsed=None
            if record['parsed'][level]!=parsed:raise PlanError('parsed_proposal_changed: استخدم resolution فقط')
    book.close()
    return request
