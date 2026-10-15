"""Structural/content traceability gate; scientific equivalence still needs human/agent review."""
import argparse, ast, operator, math, re
from pathlib import Path
from common import read_json, write_json, digest, norm, iter_blocks

OPS={ast.Add:operator.add,ast.Sub:operator.sub,ast.Mult:operator.mul,ast.Div:operator.truediv,ast.Pow:operator.pow}
def arithmetic(expr):
    tree=ast.parse(expr,mode='eval')
    def walk(n):
        if isinstance(n,ast.Expression):return walk(n.body)
        if isinstance(n,ast.Constant) and type(n.value) in [int,float]:return n.value
        if isinstance(n,ast.UnaryOp) and isinstance(n.op,(ast.USub,ast.UAdd)):return (-1 if isinstance(n.op,ast.USub) else 1)*walk(n.operand)
        if isinstance(n,ast.BinOp) and type(n.op) in OPS:
            l,r=walk(n.left),walk(n.right)
            if isinstance(n.op,ast.Pow) and abs(r)>20:raise ValueError('Unbounded exponent')
            x=OPS[type(n.op)](l,r)
            if not math.isfinite(x):raise ValueError('Nonfinite result')
            return x
        raise ValueError('Check expressions allow numeric arithmetic only; no calls/names/code.')
    return walk(tree)
def qids(blocks):
    result=[]
    for b in iter_blocks(blocks):
        if b['type'] in ['question','example']:result.append(b['question_id'])
        if b['type']=='question_group':result.extend(b['question_ids'])
    return result
def validate(p,base):
    errors=[];warnings=[]
    def require(ok,msg):
        if not ok:errors.append(msg)
    invpath=Path(p['inventory']);invpath=invpath if invpath.is_absolute() else base/invpath
    inv=read_json(invpath);require(p['source_sha256']==inv['sha256'],'Inventory hash differs from plan')
    require(digest(inv['source'])==inv['sha256'],'Original source changed')
    require(bool(re.fullmatch(r'[0-9]{1,2}',str(p.get('unit_number','')))),'Verified unit_number is required for title badge')
    require(bool(p.get('unit_source_ids')) or bool(p.get('unit_user_verified')),'Unit number needs source locator or explicit user verification')
    sourceids={x['id'] for k in ['paragraphs','tables','equations','media','objects'] for x in inv.get(k,[])}
    require(set(p.get('unit_source_ids',[]))<=sourceids,'Unit source locator not in inventory')
    disp={x['source_id']:x for x in p['source_dispositions']}
    require(len(disp)==len(p['source_dispositions']),'Duplicate source disposition')
    require(set(disp)==sourceids,'Unaccounted/unknown inventory items: '+str(sorted(sourceids^set(disp))))
    for sid,item in disp.items():
        require(item.get('status') in ['content','question','image_spec','identity','wrapper','duplicate','non_scientific'],'Invalid disposition '+sid)
        require(bool(item.get('reason')),'Missing disposition reason '+sid)
    facts={f['id']:f for f in p['facts']};require(len(facts)==len(p['facts']),'Duplicate fact IDs')
    for fid,f in facts.items():
        require(bool(f.get('statement')) and bool(f.get('source_ids')),'Fact lacks statement/provenance '+fid)
        require(set(f.get('source_ids',[]))<=sourceids,'Unknown source IDs in fact '+fid)
    mapped={sid for f in facts.values() for sid in f.get('source_ids',[])}
    for sid,item in disp.items():
        if item.get('status')=='content':require(sid in mapped,'Source content has no fact mapping '+sid)
    qs={q['id']:q for q in p['questions']};require(len(qs)==len(p['questions']),'Duplicate question IDs')
    mathids={e['id'] for e in inv.get('equations',[])}|set(p.get('new_equations',{}))
    for mid,xml in p.get('new_equations',{}).items():
        require(not re.search(r'[\u0600-\u06FF]',xml),
                'Arabic prose in editable equation may render as missing glyphs; place it in a text run '+mid)
    for qid,q in qs.items():
        require(bool(q.get('prompt')) and bool(q.get('solution')),'Missing prompt or solution '+qid)
        require(bool(q.get('fact_ids')) and set(q.get('fact_ids',[]))<=set(facts),'Question has no/unknown source facts '+qid)
        require(q.get('origin') in ['source','generated'],'Unknown question origin '+qid)
        require(set(q.get('source_ids',[]))<=sourceids,'Unknown question source locator '+qid)
        require(q.get('origin')!='source' or bool(q.get('source_ids')),'Source question needs source locator '+qid)
        require(q.get('kind') in ['example','exercise','practice','enrichment','mcq','source_question'],'Unknown question kind '+qid)
        require(q.get('difficulty') in ['easy','medium','hard'],'Unknown difficulty '+qid)
        require(bool(q.get('answer')),'Missing final answer '+qid)
        if q.get('prompt_runs'):
            require(norm(''.join(x.get('text','') for x in q['prompt_runs']))==norm(q['prompt']),'prompt_runs changed question wording '+qid)
        if q.get('numerical') or q.get('kind')=='example':
            w=q.get('worked_solution')
            require(isinstance(w,dict),'Structured equation-based worked_solution required '+qid)
            if isinstance(w,dict):
                require(bool(w.get('givens')) or w.get('givens_math_id') in mathids,'Worked givens missing '+qid)
                require(bool(w.get('target')),'Worked target missing '+qid)
                require(bool(w.get('steps')),'Numbered worked steps missing '+qid)
                for st in w.get('steps',[]):require(bool(st.get('label')) and st.get('math_id') in mathids,'Worked step needs valid editable equation '+qid)
                require(w.get('final_math_id') in mathids,'Final answer needs editable equation '+qid)
        if q.get('kind')=='mcq':
            options=q.get('options',[]);oids=[o['id'] for o in options]
            require(len(options)>=3 and len(oids)==len(set(oids)),'Invalid MCQ options '+qid)
            require(len({norm(o['text']) for o in options})==len(options),'Duplicate MCQ option text '+qid)
            require(q['answer'].get('option_id') in oids,'Invalid MCQ correct option '+qid)
            require(bool(q.get('uniqueness_reason')),'Missing unique-correct-answer reasoning '+qid)
        for c in q.get('checks',[]):
            try:
                x=arithmetic(c['expression']);require(math.isclose(x,c['expected'],rel_tol=c.get('rtol',1e-6),abs_tol=c.get('atol',1e-6)),f'Calculation check failed {qid}: {x} != {c["expected"]}')
            except Exception as e:errors.append(f'Invalid calculation check {qid}: {e}')
        if q.get('numerical'):
            require(bool(q.get('checks')),'Numerical question needs independent arithmetic check '+qid)
            require(bool(q['answer'].get('unit')),'Numerical answer missing unit '+qid)
            value=q['answer'].get('value')
            require(type(value) in [int,float],'Numerical answer needs a numeric value '+qid)
            if type(value) in [int,float]:
                require(any(math.isclose(c.get('expected',float('inf')),value,rel_tol=c.get('rtol',1e-6),abs_tol=c.get('atol',1e-6)) for c in q.get('checks',[])), 'Declared answer not verified by an independent check '+qid)
        # Teacher steps must state final answer, not only an opaque answer field in JSON.
        require(q.get('solution_reviewed') is True,'Solution not reviewed '+qid)
    for sid,item in disp.items():
        if item.get('status')=='question':require(any(sid in q.get('source_ids',[]) for q in qs.values()),'Source question unregistered '+sid)
    docs=p['documents'];expected={'student','compact','rewritten'}
    require(set(docs)==expected,'Documents must contain student, compact, rewritten exactly')
    docqs={}
    for role,blocks in docs.items():
        bs=list(iter_blocks(blocks));ids=qids(blocks);docqs[role]=ids
        require(len(ids)==len(set(ids)),'Question duplicated in '+role)
        require(set(ids)<=set(qs),'Unknown question in '+role)
        for qid in ids:
            if qid in qs:require(bool(qs[qid].get('locators',{}).get('student' if role=='rewritten' else role)),'Missing visible question locator '+role+' '+qid)
        coverage={fid for b in bs for fid in b.get('fact_ids',[])}
        # Question statements/examples contribute explicit source fact coverage too.
        coverage|={fid for qid in ids if qid in qs for fid in qs[qid]['fact_ids']}
        require(set(facts)<=coverage,'Uncovered facts in '+role+': '+str(sorted(set(facts)-coverage)))
        require(coverage<=set(facts),'Unknown fact ID in '+role)
        require(bool(blocks) and blocks[0].get('section')=='main_idea','Main idea must be first content block in '+role)
        require(any(b['type']=='glossary' for b in bs),'Glossary cards missing in '+role)
        require(any(b['type']=='final_summary' for b in bs),'Styled final summary missing in '+role)
        require(bool(blocks) and blocks[-1]['type']=='remember_at_solution','تذكّر عند الحل must close '+role)
        for b in bs:
            if b['type']=='glossary':
                require(bool(b.get('entries')),'Empty glossary '+role)
                for item in b.get('entries',[]):require(bool(item.get('term')) and not re.search(r'[A-Za-z]',item['term']),'Non-Arabic/empty glossary term '+role)
            if b['type']=='card':require(b['kind'] not in ['example','law','definition'],'Use semantic example/law/definition block rather than generic '+b['kind'])
            if b['type']=='definition':require(bool(b.get('term')) and bool(b.get('definition') or b.get('definition_runs')),'Definition needs term and body')
            if b['type']=='law':require(bool(b.get('symbols')) and bool(b.get('math_ids')),'Law missing equation/symbols')
            if b['type']=='table':require(b.get('size',10.5)==10.5,'All data tables must use 10.5 pt in '+role)
            if b['type']=='remember_at_solution':require(bool(b.get('items')),'Empty تذكّر عند الحل '+role)
            if b['type']=='figure':
                require(not re.search(r'(?:شكل|رسم)\s*[（(]?\s*\d+',b.get('caption','')),'Numbered figure wrapper survives')
            if role in ['student','compact','rewritten'] and b['type'] in ['question','question_group']:
                require('solution' not in b and 'answer' not in b,'Student question contains answer fields')
    require(set(docqs.get('student',[]))==set(docqs.get('rewritten',[])),'Rewritten edition must preserve the student question set')
    originals={q['id'] for q in qs.values() if q['origin']=='source'}
    for role,ids in docqs.items():require(originals<=set(ids),'Source question omitted in '+role)
    used={x for ids in docqs.values() for x in ids};require(used==set(qs),'Unused questions in registry')
    require(p.get('semantic_review',{}).get('status')=='passed','Semantic source-to-output review not passed')
    require(bool(p.get('semantic_review',{}).get('notes')),'Semantic review needs evidence notes')
    require(all(x.get('resolved') for x in p.get('inventory_flag_resolutions',[])),'Unresolved source extraction flags')
    require(len(p.get('inventory_flag_resolutions',[]))==len(inv['review_flags']),'Every inventory review flag needs a resolution')
    target=p.get('bank_target',120);count=len(docqs.get('compact',[]))
    bank=[qs[qid] for qid in docqs.get('compact',[]) if qid in qs]
    require(any(q['kind']=='mcq' for q in bank) or bool(p.get('mcq_omission_reason')),'Compact bank needs multiple-choice questions or a documented scope-specific reason')
    if count>=6:
        require({'easy','medium','hard'}<={q['difficulty'] for q in bank} or bool(p.get('difficulty_exception_reason')),'Bank needs easy, medium and hard/thinking levels, or a documented lesson-specific reason')
    if count<target:warnings.append(f'Bank has {count}, target {target}; document why fewer substantive questions suit this lesson.')
    require(count>=target or bool(p.get('bank_count_reason')),'Bank shortfall needs substantive pedagogical explanation')
    return {'status':'passed' if not errors else 'failed','errors':errors,'warnings':warnings,'facts':len(facts),'questions':{k:len(v) for k,v in docqs.items()},'limits':'Traceability and arithmetic checks do not prove semantic equivalence or scientific correctness. Review evidence and render every page.'}
def main():
    ap=argparse.ArgumentParser();ap.add_argument('plan');ap.add_argument('--report',required=True);a=ap.parse_args();path=Path(a.plan).resolve()
    report=validate(read_json(path),path.parent);write_json(a.report,report)
    print(report['status'],len(report['errors']),'errors',len(report['warnings']),'warnings')
    for e in report['errors']:print(e)
    raise SystemExit(1 if report['errors'] else 0)
if __name__=='__main__':main()

