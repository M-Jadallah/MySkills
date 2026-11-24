"""Pure data transformations for the student plan pipeline; no file authoring."""
from __future__ import annotations

import functools
import json
import pathlib
import re
from collections import Counter
from fractions import Fraction

from planner import PlanError, build_plan, normalize, page_rank

SKILL=pathlib.Path(__file__).resolve().parent.parent
CATALOG=json.loads((SKILL/'assets/catalog.json').read_text(encoding='utf-8'))


def clean(value):
    return re.sub(r'\s+',' ','' if value is None else str(value)).strip()


def folded(value):
    return re.sub(r'[\u064b-\u065f\u0670]','',clean(value)).replace('أ','ا').replace('إ','ا').replace('آ','ا').replace('ى','ي').replace('ة','ه')


def dedupe(items):
    return list({json.dumps(x,ensure_ascii=False,sort_keys=True):x for x in items}.values())


def named_pattern(name):
    return r'(?<![ء-ي])و?'+r'\s+'.join(re.escape(normalize(x)) for x in name.split())+r'(?![ء-ي])'


def parse_cell(value):
    """Conservative parser: reject unknown residue instead of discarding content."""
    if value is None or clean(value) in ('','-','—','لا يوجد','لايوجد','لا'):
        return []
    if isinstance(value,bool): raise PlanError('invalid_boolean')
    if isinstance(value,float) and not value.is_integer():
        raise PlanError('ambiguous_decimal: حدّد هل هذه قائمة أجزاء أم رقم عشري')
    text=folded(str(int(value)) if isinstance(value,float) else value)
    digits={ord(c):str(i) for alphabet in ('٠١٢٣٤٥٦٧٨٩','۰۱۲۳۴۵۶۷۸۹') for i,c in enumerate(alphabet)}
    text=text.translate(digits).replace('ـ',' ')
    # Enforce named-word boundaries even when سورة/جزء touches the following word.
    text=re.sub(r'(سوره|الجزء|جزء|الاجزاء)(?=[ء-ي0-9])',r'\1 ',text)
    if re.search(r'كم\s*صفح|بعض|اخر|اول|مش\s*كامل|غير\s*كامل|ناقص|نصف|ربع|فقط',text):
        raise PlanError('partial_extent: المقرر الجزئي يحتاج حدودًا دقيقة')
    if re.search(r'صفح(?:ه|ات)',text):
        remainder=re.sub(r'(?:ال)?صفح(?:ه|ات)|من|الي|الى|إلى|حتي|حتى',' ',text)
        if re.search(r'[^\d\s+(),،./_\-–—؛;:]',remainder): raise PlanError('ambiguous_page_text')
        if re.search(r'\d+\s*_\s*\d+',remainder):raise PlanError('page_list_or_range: حدّد هل الشرطة السفلية قائمة أم مدى')
        pairs=re.findall(r'(\d+)\s*(?:-|–|—|الي|الى|إلى|حتي|حتى)\s*(\d+)',re.sub(r'(?:ال)?صفح(?:ه|ات)|من',' ',text))
        if pairs:
            residue=re.sub(r'\d+\s*(?:-|–|—|الي|الى|إلى|حتي|حتى)\s*\d+',' ',re.sub(r'(?:ال)?صفح(?:ه|ات)|من',' ',text))
            if re.search(r'[^\s+(),،./\-–—؛;:]',residue): raise PlanError('ambiguous_page_ranges')
            return [{'type':'pages','from':int(a),'to':int(b)} for a,b in pairs]
        numbers=[int(x) for x in re.findall(r'\d+',text)]
        if not numbers: raise PlanError('missing_page_numbers')
        return [{'type':'pages','numbers':numbers}]
    # Named surah range is supported when the entire expression is a range.
    match=re.fullmatch(r'من\s+(?:سوره\s+)?(.+?)\s+(?:الي|الى|إلى|حتي|حتى|ل)(?:\s*سوره)?\s*(.+)',text)
    if match:
        names={folded(s['name']):s['number'] for s in CATALOG['surahs']}
        a,b=[x.strip() for x in match.groups()]
        if b not in names and 'ا'+b in names:b='ا'+b
        if a in names and b in names:
            return [{'type':'surah_range','from':names[a],'to':names[b]}]
    # Explicit numeric surah selectors are never reinterpreted as juz numbers.
    items=[]
    surah_number=re.fullmatch(r'سوره\s+(\d+)',text)
    if surah_number:
        number=int(surah_number[1])
        if not 1<=number<=114:raise PlanError('invalid_surah_number')
        return [{'type':'surah','number':number}]
    if re.search(r'سوره\s*\d',text):raise PlanError('mixed_numeric_surah: حدّد السور والأجزاء منفصلة')
    # Numeric juz ranges with explicit إلى are unambiguous.
    for match in list(re.finditer(r'(\d+)\s*(?:الي|الى|إلى|حتي|حتى)\s*(\d+)',text)):
        items.append({'type':'juz_range','from':int(match[1]),'to':int(match[2])})
        text=text.replace(match[0],' ')
    if re.search(r'(?:الي|الى|إلى|حتي|حتى)',text):
        raise PlanError('mixed_range: حدّد حدود الأجزاء والسور المختلطة')
    bare=re.sub(r'الاجزاء|اجزاء|الجزء|جزء|من',' ',text).strip()
    two=re.fullmatch(r'\s*(\d+)\s*[-_–—]\s*(\d+)\s*',bare)
    if two and abs(int(two[1])-int(two[2]))!=1:
        raise PlanError('list_or_range: هل تقصد الجزأين أم المدى بينهما؟')
    # Three-plus hyphen-only numbers are established list notation; a range-like
    # pair embedded in another expression is not covered by that convention.
    hyphen_list=re.fullmatch(r'\s*\d+(?:\s*[-_–—]\s*\d+){2,}\s*',bare)
    if not hyphen_list:
        for pair in re.finditer(r'(\d+)\s*[-_–—]\s*(\d+)',bare):
            if abs(int(pair[1])-int(pair[2]))!=1:raise PlanError('list_or_range: الشرطة داخل التعبير قد تعني مدى؛ يلزم تحديد')
    for alias,number in [('قد سمع',28),('تبارك',29),('عم',30)]:
        pattern=named_pattern(alias)
        if re.search(pattern,text):
            items.append({'type':'juz','number':number})
            text=re.sub(pattern,' ',text)
    # Longest names first prevent a short name from consuming a longer one.
    for surah in sorted(CATALOG['surahs'],key=lambda s:len(s['name']),reverse=True):
        pattern=named_pattern(surah['name'])
        if re.search(pattern,text):
            items.append({'type':'surah','number':surah['number']})
            text=re.sub(pattern,' ',text)
    for num in re.findall(r'\d+',text):
        if not 1<=int(num)<=30: raise PlanError(f'invalid_juz:{num}')
        items.append({'type':'juz','number':int(num)})
    text=re.sub(r'\d+',' ',text)
    text=re.sub(r'الاجزاء|اجزاء|الجزء|جزء|سوره|سور|من',' ',text)
    residue=re.sub(r'[\s+(),،./_\-–—؛;:]+|(?<![ء-ي])و(?![ء-ي])','',text)
    if residue: raise PlanError(f'unparsed_text:{residue}')
    if not items: raise PlanError('missing_segments')
    return dedupe(items)


def range_pages(label):
    ranges=re.findall(r'\((\d+) - (\d+)\)',label)
    if not ranges: raise PlanError(f'invalid_cumulative_label:{label}')
    return [p for a,b in ranges for p in range(int(a),int(b)+1)]


def component(name,segments,category,settings,overlap='error'):
    if not segments: return {'category':category,'rows':[],'units':[],'notices':[]}
    spec={'student_name':name,'segments':segments,'cumulative_pages':settings['cumulative_pages'],'allow_short_units':settings['allow_short_units']}
    if overlap=='independent': spec['overlap_policy']='independent'
    plan=build_plan(spec,CATALOG)
    endpoint=None
    events=[]
    for seq,original in enumerate(plan['rows']):
        row=list(original)
        kind='test' if row[6]==1 else 'page' if type(row[2]) is int else 'cumulative'
        if kind=='page': endpoint=row[2]
        elif kind=='cumulative': endpoint=range_pages(row[2])[-1]
        if category=='medium':
            if kind=='page': continue
            if kind=='cumulative': row[4]=len(range_pages(row[2]))
        else: row[4]=original[4]*2
        events.append({'row':row,'category':category,'kind':kind,'endpoint':endpoint,'sequence':seq,'original_weight':original[4]})
    return {**plan,'rows':events,'category':category,'spec':spec}


def boundary_only(a,b,shared):
    return a['kind']==b['kind']=='surah' and len(shared)==1 and (a['last_page']==b['first_page'] or b['last_page']==a['first_page'])


def exact_number(value):
    return int(value) if value.denominator==1 else float(value)


def partition(weights,exceptions=False):
    weights=[Fraction(str(w)) for w in weights]
    if not weights or any(w<0 for w in weights): raise PlanError('invalid_weights')
    n=len(weights)
    cap=sum(weights)/8
    prefix=[Fraction()]
    for w in weights: prefix.append(prefix[-1]+w)
    def valid(i,j): return prefix[j]-prefix[i]<=cap or (exceptions and j==i+1 and weights[i]>cap)
    @functools.lru_cache(None)
    def possible(i,k):
        if k==1: return i<n
        return any(valid(i,j) and possible(j,k-1) for j in range(i+1,n-k+2))
    if not possible(0,8): return None
    groups=[]
    i=0
    for k in range(8,1,-1):
        choices=[j for j in range(i+1,n-k+2) if valid(i,j) and possible(j,k-1)]
        end=max(choices,key=lambda j:(prefix[j]-prefix[i],j))
        groups.append((i,end))
        i=end
    return groups+[(i,n)]


def group_rows(rows):
    unchanged=len(rows)<=8
    if unchanged: ranges=[(i,i+1) for i in range(len(rows))]; exception=False
    else:
        ranges=partition([r[4] for r in rows]); exception=ranges is None
        if exception: ranges=partition([r[4] for r in rows],True)
        if ranges is None: raise PlanError('partition_impossible')
    groups=[]
    for index,(start,end) in enumerate(ranges,1):
        originals=rows[start:end]
        weight=exact_number(sum((Fraction(str(r[4])) for r in originals),Fraction()))
        if len(originals)==1:
            row=list(originals[0]); row[0],row[1]=None,index
        else: row=[None,index,' + '.join(str(r[2]) for r in originals),None,weight,None,None,None,None,None,None]
        groups.append({'row':row,'source_start':start+2,'source_end':end+1,'source_count':end-start,'weight':weight})
    return {'unchanged':unchanged,'allow_oversized_singletons':exception,'groups':groups,'grouped_rows':[g['row'] for g in groups]}


def student_plan(name,medium,weak,settings,overlap='error'):
    components=[component(name,segs,cat,settings,overlap) for cat,segs in [('medium',medium),('weak',weak)]]
    for a in components[0]['units']:
        for b in components[1]['units']:
            shared=set(a['pages'])&set(b['pages'])
            if shared and not boundary_only(a,b,shared) and overlap!='independent':
                raise PlanError(f'cross_level_overlap:{a["name"]}/{b["name"]}: احسم التصنيف أو المراجعة المستقلة')
    events=[e for c in components for e in c['rows']]
    events.sort(key=lambda e:(page_rank(e['endpoint']),0 if e['category']=='medium' else 1,e['sequence']))
    if not events: raise PlanError('empty_student_plan')
    for i,e in enumerate(events,1): e['row'][0],e['row'][1]=None,i
    rows=[e['row'] for e in events]
    total=sum(r[4] for r in rows)
    return {'name':name,'components':components,'events':events,'rows':rows,'original_count':len(rows),'total_weight':total,'medium_weight':sum(e['row'][4] for e in events if e['category']=='medium'),'weak_weight':sum(e['row'][4] for e in events if e['category']=='weak'),'daily_weight':exact_number(Fraction(str(total))/8),**group_rows(rows),'notices':list(dict.fromkeys(n for c in components for n in c['notices']))}


def safe_names(students):
    sheets={'الإحصائيات'.casefold()}
    files=set()
    for student in students:
        name=student['name']
        stem=re.sub(r'[<>:"/\\|?*\x00-\x1f]',' ',name)
        stem=clean(stem).strip(' .')
        if not stem or len(stem)>150: raise PlanError(f'invalid_filename:{name}')
        if re.fullmatch(r'CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9]',stem,re.I): stem='الطالب '+stem
        if stem.casefold() in files: raise PlanError(f'filename_collision:{name}')
        files.add(stem.casefold()); student['file_stem']=stem
        base=re.sub(r'[\[\]:*?/\\]',' ',name).strip(" '") or 'طالب'
        candidate=base[:31]
        number=2
        while candidate.casefold() in sheets:
            suffix=f' ({number})'; candidate=base[:31-len(suffix)]+suffix; number+=1
        sheets.add(candidate.casefold()); student['sheet_name']=candidate
