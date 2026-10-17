"""Place an editable unit-number badge beside the retained title box."""
from copy import deepcopy
import re
from lxml import etree as E
from docx.oxml import OxmlElement

N={
 'w':'http://schemas.openxmlformats.org/wordprocessingml/2006/main',
 'mc':'http://schemas.openxmlformats.org/markup-compatibility/2006',
 'wp':'http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing',
 'a':'http://schemas.openxmlformats.org/drawingml/2006/main',
 'wps':'http://schemas.microsoft.com/office/word/2010/wordprocessingShape',
 'v':'urn:schemas-microsoft-com:vml',
 'w14':'http://schemas.microsoft.com/office/word/2010/wordml',
}
def tag(p,n):return '{'+N[p]+'}'+n
def _set_size(pr,halfpoints):
    for n in ('sz','szCs'):
        e=pr.find(tag('w',n))
        if e is None:e=E.SubElement(pr,tag('w',n))
        e.set(tag('w','val'),str(halfpoints))
    color=pr.find(tag('w','color'))
    if color is None:color=E.SubElement(pr,tag('w','color'))
    color.set(tag('w','val'),'FFFFFF')
    for n in ('b','bCs'):
        e=pr.find(tag('w',n))
        if e is None:e=E.SubElement(pr,tag('w',n))
        e.set(tag('w','val'),'1')

def set_title_and_unit(doc,title,unit_number):
    if not re.fullmatch(r'[0-9]{1,2}',str(unit_number)):
        raise ValueError('unit_number must be a verified one- or two-digit numeral')
    seen=set()
    for sec in doc.sections:
        for header in (sec.header,sec.first_page_header,sec.even_page_header):
            h=header._element
            if id(h) in seen:continue
            seen.add(id(h))
            for t in h.iter(tag('w','t')):
                if t.text=='{{LESSON_TITLE}}':t.text=title
            # The approved template has one title text box with both DrawingML
            # and VML branches. Clone it so the new badge uses the same anchor
            # coordinate system and remains editable in either Word branch.
            title_ac=None
            for ac in h.iter(tag('mc','AlternateContent')):
                if any(t.text==title for t in ac.iter(tag('w','t'))):title_ac=ac;break
            if title_ac is None:continue
            if any(p.get('name')=='AltayfUnitBadge' for p in h.iter(tag('wp','docPr'))):continue
            badge=deepcopy(title_ac)
            for t in badge.iter(tag('w','t')):t.text='الوحدة '+str(unit_number)
            for rp in badge.iter(tag('w','rPr')):_set_size(rp,21)
            for pp in badge.iter(tag('w','pPr')):
                jc=pp.find(tag('w','jc'))
                if jc is None:jc=E.SubElement(pp,tag('w','jc'))
                jc.set(tag('w','val'),'center')
            anchor=badge.find('.//wp:anchor',N)
            if anchor is not None:
                anchor.find('.//wp:positionH/wp:posOffset',N).text='1494000' # x 4.15 cm
                anchor.find('.//wp:positionV/wp:posOffset',N).text='450000'  # y 1.25 cm
                ext=anchor.find('wp:extent',N);ext.set('cx','612000');ext.set('cy','300000')
                shape_ext=anchor.find('.//wps:spPr/a:xfrm/a:ext',N)
                if shape_ext is not None:shape_ext.set('cx','612000');shape_ext.set('cy','300000')
                dp=anchor.find('wp:docPr',N);dp.set('id','20260930');dp.set('name','AltayfUnitBadge')
                shape=anchor.find('.//wps:spPr',N)
                if shape is not None:
                    for nofill in list(shape.findall('a:noFill',N)):shape.remove(nofill)
                    fill=E.Element(tag('a','solidFill'));E.SubElement(fill,tag('a','srgbClr'),val='082C5A')
                    ln=shape.find(tag('a','ln'))
                    shape.insert(list(shape).index(ln) if ln is not None else len(shape),fill)
                    if ln is not None:
                        for child in list(ln):
                            if child.tag in (tag('a','noFill'),tag('a','solidFill')):ln.remove(child)
                        sf=E.Element(tag('a','solidFill'));E.SubElement(sf,tag('a','srgbClr'),val='082C5A');ln.insert(0,sf)
            vshape=badge.find('.//v:shape',N)
            if vshape is not None:
                vshape.set('id','AltayfUnitBadgeVML');vshape.set('fillcolor','#082C5A');vshape.set('strokecolor','#082C5A')
                style=vshape.get('style','')
                changes={'margin-left':'117.6pt','margin-top':'35.4pt','width':'48.2pt','height':'23.6pt'}
                for k,v in changes.items():style=re.sub(r'(^|;)'+re.escape(k)+r':[^;]*',lambda m:m.group(1)+k+':'+v,style)
                vshape.set('style',style)
                for t in vshape.iter(tag('w','t')):t.text='الوحدة '+str(unit_number)
            run=OxmlElement('w:r');run.append(badge)
            source_run=title_ac.getparent()
            source_run.addnext(run)
