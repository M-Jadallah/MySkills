"""Create genuine Office SmartArt and transplant its complete OOXML model.

Only Word's SmartArt engine generates geometry. This module preserves semantic
data, layout, style, colors and native cached drawing; it never simulates a map
with standalone shapes, VML, pictures or text boxes.
"""
from __future__ import annotations
import copy
import json
import os
import re
import subprocess
import tempfile
from collections import Counter
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED
from lxml import etree

N = {
    'w':'http://schemas.openxmlformats.org/wordprocessingml/2006/main',
    'a':'http://schemas.openxmlformats.org/drawingml/2006/main',
    'dgm':'http://schemas.openxmlformats.org/drawingml/2006/diagram',
    'dsp':'http://schemas.microsoft.com/office/drawing/2008/diagram',
    'wp':'http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing',
    'r':'http://schemas.openxmlformats.org/officeDocument/2006/relationships',
    'rel':'http://schemas.openxmlformats.org/package/2006/relationships',
    'ct':'http://schemas.openxmlformats.org/package/2006/content-types',
}


def q(prefix, local):
    return '{'+N[prefix]+'}'+local


def xml_bytes(root):
    return etree.tostring(root, xml_declaration=True, encoding='UTF-8', standalone=True)


def solid(parent, color):
    for child in list(parent):
        if etree.QName(child).localname in ('noFill','solidFill','gradFill','pattFill','blipFill','grpFill'):
            parent.remove(child)
    fill=etree.SubElement(parent,q('a','solidFill'))
    etree.SubElement(fill,q('a','srgbClr'),val=color)


def style_shape(sppr, colors, fill=None, rounded=False, root=False, connector=False):
    line=sppr.find(q('a','ln'))
    if line is None:
        line=etree.SubElement(sppr,q('a','ln'))
    line.set('w',str(12700 if root else 7000))
    solid(line,colors['secondary'] if connector else colors['accent'] if root else colors['line'])
    if rounded:
        old=sppr.find(q('a','prstGeom'))
        if old is not None:
            sppr.remove(old)
        geom=etree.Element(q('a','prstGeom'),prst='roundRect')
        av=etree.SubElement(geom,q('a','avLst'))
        etree.SubElement(av,q('a','gd'),name='adj',fmla='val 9000')
        # Geometry precedes fills and lines in CT_ShapeProperties.
        sppr.insert(1 if sppr.find(q('a','xfrm')) is not None else 0,geom)
    if fill:
        solid(sppr,fill)
    order={'xfrm':0,'custGeom':1,'prstGeom':1,'noFill':2,'solidFill':2,'gradFill':2,'blipFill':2,'pattFill':2,'grpFill':2,'ln':3,'effectLst':4,'effectDag':4,'scene3d':5,'sp3d':6,'extLst':7}
    sppr[:]=sorted(sppr,key=lambda x:order.get(etree.QName(x).localname,99))


def normalize_text(root, font):
    for text_body in root.xpath('//dgm:t | //dsp:txBody',namespaces=N):
        for paragraph in text_body.findall(q('a','p')):
            pp=paragraph.find(q('a','pPr'))
            if pp is None:
                pp=etree.Element(q('a','pPr'));paragraph.insert(0,pp)
            pp.set('rtl','1');pp.set('algn','ctr')
        for rp in text_body.xpath('.//a:rPr | .//a:defRPr | .//a:endParaRPr',namespaces=N):
            rp.set('lang','ar-SA')
            for role in ('latin','ea','cs'):
                face=rp.find(q('a',role))
                if face is None:face=etree.SubElement(rp,q('a',role))
                face.set('typeface',font)
            # Script face order is significant to OOXML validators.
            order={'ln':0,'noFill':1,'solidFill':1,'gradFill':1,'blipFill':1,'pattFill':1,'grpFill':1,'effectLst':2,'effectDag':2,'highlight':3,'uLnTx':4,'uLn':4,'uFillTx':5,'uFill':5,'latin':6,'ea':7,'cs':8,'sym':9,'hlinkClick':10,'hlinkMouseOver':11,'rtl':12,'extLst':13}
            rp[:]=sorted(rp,key=lambda x:order.get(etree.QName(x).localname,99))


def resolve_palette(root, design):
    colors=design['colors']
    roles={'accent1':'secondary','accent2':'primary','accent3':'accent','accent4':'tint','accent5':'secondary','accent6':'accent','dk1':'ink','lt1':'white','dk2':'primary','lt2':'tint','hlink':'secondary','folHlink':'primary','phClr':'secondary','tx1':'ink','tx2':'primary','bg1':'white','bg2':'tint'}
    for color in root.xpath('//a:schemeClr',namespaces=N):
        role=roles.get(color.get('val'))
        if role:
            color.tag=q('a','srgbClr');color.set('val',colors[role])


def polish_data(root, design, hierarchy):
    colors=design['colors']
    for point in root.xpath('//dgm:pt',namespaces=N):
        sppr=point.find(q('dgm','spPr'))
        if sppr is None:continue
        label=''.join(point.xpath('./dgm:t//a:t/text()',namespaces=N))
        if label:
            current=sppr.xpath('./a:solidFill/a:srgbClr/@val',namespaces=N)
            fill=current[0] if current else colors['tint']
            style_shape(sppr,colors,fill,hierarchy,fill==colors['primary'])
    normalize_text(root,design['font'])


def polish_drawing(root, design, hierarchy):
    colors=design['colors']
    for shape in root.xpath('//dsp:sp',namespaces=N):
        sppr=shape.find(q('dsp','spPr'))
        if sppr is None:continue
        label=''.join(shape.xpath('./dsp:txBody//a:t/text()',namespaces=N))
        if label:
            values=sppr.xpath('./a:solidFill/a:srgbClr/@val',namespaces=N)
            fill=values[0] if values else colors['tint']
            style_shape(sppr,colors,fill,hierarchy,fill==colors['primary'])
        else:
            style_shape(sppr,colors,connector=True)
    normalize_text(root,design['font'])


def create_native(plan, output):
    if os.name!='nt':
        raise RuntimeError('Genuine SmartArt generation requires Microsoft Word on Windows. No ordinary-shape or image fallback is permitted.')
    command=['powershell.exe','-NoProfile','-NonInteractive','-ExecutionPolicy','Bypass','-STA','-File',str(Path(__file__).with_name('create_smartart.ps1')),'-PlanJson',str(plan),'-OutputDoc',str(output)]
    panel_count=len(json.loads(plan.read_text(encoding='utf-8'))['panels'])
    result=subprocess.run(command,capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=max(600,90*panel_count),creationflags=subprocess.CREATE_NO_WINDOW)
    if result.returncode or not output.is_file():
        raise RuntimeError('Native Word SmartArt creation failed. '+result.stdout+'\n'+result.stderr)


def graft(base_doc, native_doc, out, plan):
    with ZipFile(base_doc) as z:base={name:z.read(name) for name in z.namelist()}
    with ZipFile(native_doc) as z:native={name:z.read(name) for name in z.namelist()}
    body=etree.fromstring(base['word/document.xml'])
    native_body=etree.fromstring(native['word/document.xml'])
    rels=etree.fromstring(base['word/_rels/document.xml.rels'])
    native_rels=etree.fromstring(native['word/_rels/document.xml.rels'])
    mapping={}
    native_targets={}
    existing={r.get('Id') for r in rels}
    for relation in native_rels:
        if 'diagram' not in relation.get('Type','').lower():continue
        i=1
        while 'rIdSA'+str(i) in existing:i+=1
        rid='rIdSA'+str(i);existing.add(rid)
        mapping[relation.get('Id')]=rid
        native_targets[relation.get('Id')]='word/'+relation.get('Target')
        copied=copy.deepcopy(relation);copied.set('Id',rid);rels.append(copied)
    if not mapping:raise RuntimeError('Office did not emit native SmartArt relationships')
    plan_by_name={'lm_smartart_'+p['id']:p for p in plan['panels']}
    part_plan={}
    replacements={}
    for drawing in native_body.xpath('//w:drawing[a:graphic or wp:inline or wp:anchor]',namespaces=N):
        props=drawing.find('.//'+q('wp','docPr'))
        if props is None or props.get('name') not in plan_by_name:continue
        panel=plan_by_name[props.get('name')]
        copied=copy.deepcopy(drawing)
        refs=copied.find('.//'+q('dgm','relIds'))
        if refs is None:raise RuntimeError('A requested graphic is not SmartArt')
        for key,value in list(refs.attrib.items()):
            if value not in mapping:raise RuntimeError('SmartArt relationship is missing')
            part_plan[native_targets[value]]=panel
            refs.set(key,mapping[value])
        data_part=native_targets[drawing.find('.//'+q('dgm','relIds')).get(q('r','dm'))]
        data_root=etree.fromstring(native[data_part])
        for extension in data_root.xpath('//*[local-name()="dataModelExt"]'):
            old=extension.get('relId')
            if old in native_targets:part_plan[native_targets[old]]=panel
        copied.find('.//'+q('wp','docPr')).set('id',str(1000+len(replacements)))
        replacements['[[SMARTART:'+panel['id']+']]']=copied
    if len(replacements)!=len(plan['panels']):raise RuntimeError('Office omitted a requested SmartArt panel')
    for text in body.xpath('//w:t',namespaces=N):
        if text.text in replacements:
            run=text.getparent()
            run.remove(text);run.append(replacements.pop(text.text))
    if replacements:raise RuntimeError('SmartArt placeholders were not found in base document')
    for name,blob in native.items():
        if not name.startswith('word/diagrams/') or not name.endswith('.xml'):continue
        root=etree.fromstring(blob)
        resolve_palette(root,plan['design'])
        panel=part_plan.get(name)
        hierarchy=panel is not None and panel['kind'] in ('tree','decision')
        for element in root.iter():
            for key,value in list(element.attrib.items()):
                if (key.startswith('{'+N['r']+'}') or key=='relId') and value in mapping:
                    element.set(key,mapping[value])
        if root.tag==q('dgm','dataModel'):polish_data(root,plan['design'],hierarchy)
        elif root.tag==q('dsp','drawing'):polish_drawing(root,plan['design'],hierarchy)
        base[name]=xml_bytes(root)
    content_types=etree.fromstring(base['[Content_Types].xml'])
    present={x.get('PartName') for x in content_types}
    for override in etree.fromstring(native['[Content_Types].xml']):
        if '/word/diagrams/' in override.get('PartName','') and override.get('PartName') not in present:
            content_types.append(copy.deepcopy(override))
    base['word/document.xml']=xml_bytes(body)
    base['word/_rels/document.xml.rels']=xml_bytes(rels)
    base['[Content_Types].xml']=xml_bytes(content_types)
    out.parent.mkdir(parents=True,exist_ok=True)
    temp_out=out.with_suffix('.writing.docx')
    with ZipFile(temp_out,'w',ZIP_DEFLATED) as z:
        for name,blob in base.items():z.writestr(name,blob)
    temp_out.replace(out)


def materialize(doc, panels, output, design, work_dir=None):
    if not panels:
        output.parent.mkdir(parents=True,exist_ok=True);doc.save(output);return
    work_dir=Path(work_dir or Path.cwd()/'work'/'smartart-build').resolve()
    work_dir.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='native-',dir=work_dir) as scratch:
        scratch=Path(scratch).resolve()
        if not scratch.is_relative_to(work_dir):raise RuntimeError('Unexpected work directory')
        base=scratch/'base.docx';native=scratch/'native.docx';plan_path=scratch/'plan.json'
        plan={'design':design,'panels':panels}
        plan_path.write_text(json.dumps(plan,ensure_ascii=False,indent=2),encoding='utf-8')
        doc.save(base)
        create_native(plan_path,native)
        graft(base,native,output,plan)


def validate_smartart(package, main, panels, font):
    errors=[];texts=[];seen=set()
    normalize=lambda value:' '.join(value.split())
    expected={'lm_smartart_'+p['id']:p for p in panels}
    rels={r.get('Id'):r for r in etree.fromstring(package.read('word/_rels/document.xml.rels'))}
    if main.xpath('//w:pict | //v:group',namespaces=dict(N,v='urn:schemas-microsoft-com:vml')):
        errors.append('Ordinary shapes/VML are forbidden for lesson maps; genuine SmartArt is required')
    for graphic in main.xpath('//a:graphicData',namespaces=N):
        if graphic.get('uri')!=N['dgm']:
            errors.append('A body graphic is not native SmartArt')
    def wanted_label(node):
        return normalize((node.get('relation','')+' '+node['label']).strip())
    def wanted_tree(node):
        return wanted_label(node),tuple(wanted_tree(c) for c in node.get('children',[]))
    for refs in main.xpath('//dgm:relIds',namespaces=N):
        drawing=refs.xpath('ancestor::w:drawing[1]',namespaces=N)[0]
        props=drawing.find('.//'+q('wp','docPr'))
        name=props.get('name') if props is not None else ''
        if name not in expected:
            errors.append('Unrecognized native SmartArt panel: '+name);continue
        if name in seen:errors.append('Duplicate SmartArt panel: '+name)
        seen.add(name);plan=expected[name]
        loaded={}
        for role in ('dm','lo','qs','cs'):
            rid=refs.get(q('r',role));relation=rels.get(rid)
            if relation is None:
                errors.append('Broken native SmartArt relationship '+name+': '+role);continue
            path='word/'+relation.get('Target')
            if path not in package.namelist():
                errors.append('Missing native SmartArt part: '+path);continue
            loaded[role]=etree.fromstring(package.read(path))
        if len(loaded)!=4:continue
        if loaded['dm'].tag!=q('dgm','dataModel') or loaded['lo'].tag!=q('dgm','layoutDef'):
            errors.append('SmartArt data/layout parts have invalid root types: '+name);continue
        if loaded['lo'].get('uniqueId')!=plan['layout_id']:
            errors.append('SmartArt uses the wrong semantic layout: '+name)
        points={p.get('modelId'):p for p in loaded['dm'].xpath('./dgm:ptLst/dgm:pt',namespaces=N)}
        labels={key:normalize(' '.join(p.xpath('./dgm:t//a:t/text()',namespaces=N))) for key,p in points.items() if p.get('type','node')=='node'}
        labels={key:label for key,label in labels.items() if label}
        children={key:[] for key in points};parent={}
        for edge in loaded['dm'].xpath('./dgm:cxnLst/dgm:cxn',namespaces=N):
            if edge.get('type','parOf')!='parOf':continue
            src,dst=edge.get('srcId'),edge.get('destId')
            if src not in points or dst not in points:
                errors.append('Dangling SmartArt parent/child relation: '+name);continue
            children[src].append((int(edge.get('srcOrd','0')),dst));parent[dst]=src
        for key in children:children[key].sort(key=lambda pair:pair[0])
        roots=[key for key in labels if parent.get(key) not in labels]
        def actual_tree(key, trail=()):
            if key in trail:raise ValueError('Cyclic hierarchy')
            return labels[key],tuple(actual_tree(child,trail+(key,)) for _,child in children.get(key,[]) if child in labels)
        try:
            if 'root' in plan:
                if len(roots)!=1 or actual_tree(roots[0])!=wanted_tree(plan['root']):
                    errors.append('SmartArt hierarchy changed node order, levels or parentage: '+name)
            else:
                doc_points=[key for key,p in points.items() if p.get('type')=='doc']
                ordered=[child for _,child in children.get(doc_points[0],[]) if child in labels] if doc_points else roots
                if [labels[key] for key in ordered]!=[wanted_label(node) for node in plan['nodes']]:
                    errors.append('SmartArt process/cycle changed the source sequence: '+name)
        except (ValueError,RecursionError):errors.append('Invalid SmartArt hierarchy: '+name)
        texts.extend(labels.values())
        cached=[]
        for extension in loaded['dm'].xpath('//*[local-name()="dataModelExt"]'):
            relation=rels.get(extension.get('relId'))
            if relation is None:continue
            cache_path='word/'+relation.get('Target')
            if cache_path not in package.namelist():continue
            cache=etree.fromstring(package.read(cache_path));cached.append(cache)
            cached_labels=[normalize(' '.join(p.xpath('.//a:t/text()',namespaces=N))) for p in cache.xpath('//dsp:txBody',namespaces=N)]
            cached_labels=[label for label in cached_labels if label]
            if Counter(cached_labels)!=Counter(labels.values()):
                errors.append('SmartArt preview cache omits or changes node text: '+name)
            for scale in cache.xpath('//a:normAutofit/@fontScale',namespaces=N):
                if int(scale)<90000:errors.append('SmartArt shrank text excessively; split the map: '+name)
        if not cached:errors.append('Native SmartArt cached drawing is missing: '+name)
        for part in [loaded['dm']]+cached:
            for run in part.xpath('//a:r[a:t]',namespaces=N):
                rp=run.find(q('a','rPr'))
                if rp is None or any(rp.find(q('a',role)) is None or rp.find(q('a',role)).get('typeface')!=font for role in ('latin','ea','cs')):
                    errors.append('SmartArt text does not use Traditional Arabic: '+name);break
    for name in expected.keys()-seen:errors.append('Required native SmartArt panel is missing: '+name)
    return {'errors':errors,'texts':texts,'count':len(seen)}
