"""Build an editable Arabic Saadi course from validated, fully vocalized JSON."""
import argparse
import json
from copy import deepcopy
from pathlib import Path
from docx import Document
from docx.shared import Pt,Cm,RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.opc.constants import RELATIONSHIP_TYPE as RT
from validate_course import validate

ROOT = Path(__file__).resolve().parents[1]
COLORS = {'black':'000000','quran':'7A1F3D','green':'154F42','gold':'8C691F','pale':'E8F1ED','gray':'E5EAE7','muted':'5E6D67'}

def ar(value): return str(value).translate(str.maketrans('0123456789','٠١٢٣٤٥٦٧٨٩'))
def el(tag, **attrs):
    e = OxmlElement('w:' + tag)
    for key,value in attrs.items(): e.set(qn('w:' + key), str(value))
    return e

class Builder:
    def __init__(self, course, font_name='Noto Naskh Arabic'):
        self.data = course
        self.font_name = font_name
        self.doc = Document(ROOT / 'assets' / 'template.docx')
        body = self.doc.element.body
        for child in list(body):
            if child.tag != qn('w:sectPr'): body.remove(child)
        self._styles()
        self._page_furniture()

    def _styles(self):
        for name,size,leading,color,bold in [
            ('Normal',14.5,27,'black',False),('Small',11.5,19,'black',False),
            ('Title',30,48,'black',True),('Subtitle',22,36,'black',True),
            ('Heading 1',23,38,'green',True),('Heading 2',17,28,'green',True),
            ('Heading 3',15,24,'gold',True),('Quran',16.5,30,'quran',True),
            ('Question',14,25,'black',True),('Option',13,23,'black',False),
            ('Answer',12.5,21,'black',False)]:
            style = self.doc.styles[name]
            style.font.name = self.font_name; style.font.size = Pt(size)
            style.font.bold = bold; style.font.italic = False
            style.font.color.rgb = RGBColor.from_string(COLORS[color])
            pr = style.element.get_or_add_rPr()
            for tag in ['bCs','iCs','szCs']:
                for old in list(pr.findall(qn('w:' + tag))): pr.remove(old)
            for attr in ['ascii','hAnsi','cs','eastAsia']: pr.rFonts.set(qn('w:' + attr),self.font_name)
            pr.append(el('bCs',val='1' if bold else '0')); pr.append(el('iCs',val='0'))
            pr.append(el('szCs',val=int(size*2)))
            pf = style.paragraph_format
            pf.line_spacing = Pt(leading); pf.space_after = Pt(5); pf.space_before = Pt(0)
            pf.widow_control = True
            pf.keep_with_next = name.startswith('Heading') or name == 'Question'
            pf.keep_together = name.startswith('Heading') or name in ['Question','Quran']
            if name in ['Title','Subtitle']:
                ppr = style.element.get_or_add_pPr()
                for child in list(ppr):
                    if child.tag in [qn('w:pBdr'),qn('w:shd'),qn('w:numPr')]: ppr.remove(child)

    def run(self,p,text,size=14.5,bold=False,color='black'):
        r = p.add_run(text)
        r.font.name = self.font_name; r.font.size = Pt(size)
        r.font.bold = bold; r.font.italic = False
        r.font.color.rgb = RGBColor.from_string(COLORS.get(color,color))
        pr = r._r.get_or_add_rPr(); rf = pr.rFonts; rf.attrib.clear()
        for key in ['ascii','hAnsi','cs','eastAsia']: rf.set(qn('w:' + key),self.font_name)
        pr.append(el('bCs',val='1' if bold else '0')); pr.append(el('iCs',val='0'))
        pr.append(el('szCs',val=round(size*2))); pr.append(el('rtl'))
        pr.append(el('lang',val='ar-SA',bidi='ar-SA'))
        return r

    def para(self,text='',style='Normal',size=None,bold=False,color='black',page=False,keep=False,center=False):
        p = self.doc.add_paragraph(style=style)
        self.configure(p,page,keep,center)
        size = size or self.doc.styles[style].font.size.pt
        import re
        for token in re.split(r'(﴿.*?﴾)',text):
            if token: self.run(p,token,size,bold or token.startswith('﴿'),'quran' if token.startswith('﴿') else color)
        return p

    @staticmethod
    def configure(p,page=False,keep=False,center=False):
        pr = p._p.get_or_add_pPr()
        if pr.find(qn('w:bidi')) is None: pr.append(el('bidi'))
        # Word mirrors left/right in a bidi paragraph; this produces right
        # alignment in the approved Word template. Check other renderers.
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER if center else WD_ALIGN_PARAGRAPH.LEFT
        p.paragraph_format.keep_with_next = keep
        p.paragraph_format.page_break_before = page

    def heading(self,text,level=1,page=False,anchor=None):
        p = self.para(text,f'Heading {level}',bold=True,color='green' if level<3 else 'gold',page=page,keep=True)
        p.paragraph_format.space_before = Pt(5 if level==1 else 8)
        p.paragraph_format.space_after = Pt(7)
        if level==1: p._p.get_or_add_pPr().append(el('shd',val='clear',fill=COLORS['pale']))
        if anchor: self.bookmark(p,anchor)
        return p

    def bookmark(self,p,name):
        number = len(self.doc.element.xpath('//w:bookmarkStart')) + 1
        p._p.insert(0,el('bookmarkStart',id=number,name=name)); p._p.append(el('bookmarkEnd',id=number))

    def _page_furniture(self):
        for section in self.doc.sections:
            section.different_first_page_header_footer = True
            section.page_width=Cm(21); section.page_height=Cm(29.7)
            section.top_margin=Cm(1.9); section.bottom_margin=Cm(1.75)
            section.left_margin=Cm(2); section.right_margin=Cm(2)
            for container in [section.first_page_header,section.first_page_footer]:
                for p in container.paragraphs:
                    for t in p._p.xpath('.//w:t'): t.text=''
            hp=section.header.paragraphs[0]
            for t in hp._p.xpath('.//w:t'): t.text=''
            self.configure(hp)
            self.run(hp,self.data['program_name'],10.5,False,'muted')
            fp=section.footer.paragraphs[0]
            # The template already contains a PAGE field. Replace text only.
            first=True
            for t in fp._p.xpath('.//w:t'):
                if t.getparent().getparent().tag==qn('w:fldSimple'): continue
                if first: t.text=self.data['program_name']+'   •   '; first=False
                else: t.text=''

    def scripture(self,text,anchor=None,center=False):
        p = self.para(text,'Quran',bold=True,color='quran',center=center)
        p.paragraph_format.keep_together=True
        p.paragraph_format.space_after=Pt(7)
        if anchor:self.bookmark(p,anchor)
        return p

    def separator(self,text,color,border_color,before=0):
        p=self.para(text,'Small',bold=True,color=color,keep=True)
        p.paragraph_format.space_before=Pt(before);p.paragraph_format.space_after=Pt(4)
        borders=el('pBdr');borders.append(el('top',val='single',sz=4,space=4,color=COLORS[border_color]))
        p._p.get_or_add_pPr().append(borders)
        return p

    def hyperlink(self,label,url):
        p=self.para('',style='Small')
        h=OxmlElement('w:hyperlink');h.set(qn('r:id'),p.part.relate_to(url,RT.HYPERLINK,is_external=True))
        tmp=self.run(p,label,11.5,False,'green');h.append(tmp._r);p._p.append(h)
        return p

    def build(self):
        p=self.para(self.data['cover_title'],'Title',30,True,page=False,keep=True,center=True)
        p.paragraph_format.space_before=Pt(210);p.paragraph_format.space_after=Pt(20)
        self.para(self.data['course_title'],'Subtitle',22,True,center=True)
        for ui,unit in enumerate(self.data['units']):
            self.heading(unit['title'],page=True,anchor=f'unit_{ui}')
            self.para(unit['scope'],'Small')
            if unit.get('basmala'):self.scripture(unit['basmala'],center=True)
            for bi,block in enumerate(unit['blocks']):
                suffix='  الْآيَاتُ '+ar(block['start_ayah'])+' إِلَى '+ar(block['end_ayah'])
                self.heading(block['title']+suffix,2,anchor=f'block_{ui}_{bi}')
                self.separator('الْآيَاتُ الْكَرِيمَةُ','quran','quran',7)
                ayahs=' '.join(a['text']+' ﴿'+ar(a['number'])+'﴾' for a in block['ayahs'])
                self.scripture(ayahs)
                self.separator('التَّفْسِيرُ','black','gray')
                for pi,item in enumerate(block['paragraphs']):
                    p=self.para('')
                    self.bookmark(p,f'tafsir_{ui}_{bi}_{pi}')
                    for segment in item['segments']:
                        scripture=segment['kind']=='quran'
                        text='﴿'+segment['text']+'﴾' if scripture else segment['text']
                        self.run(p,text,14.5,scripture,'quran' if scripture else 'black')

        self.heading('الْأَسْئِلَةُ',page=True,anchor='questions')
        self.para('اخْتَرْ إِجَابَةً وَاحِدَةً لِكُلِّ سُؤَالٍ، وَضَعْ عَلَامَةً فِي خَانَةِ صَحٍّ أَوْ خَطَأٍ لِكُلِّ عِبَارَةٍ.','Small')
        mcq=[q for q in self.data['questions'] if q['type']=='mcq']
        letters=['أ','ب','ج','د']
        self.heading('الِاخْتِيَارُ مِنْ مُتَعَدِّدٍ',2)
        for index,q in enumerate(mcq):
            if index and index%5==0:self.heading('الِاخْتِيَارُ مِنْ مُتَعَدِّدٍ تَابِعٌ',2,page=True)
            p=self.para(ar(q['id'])+'  '+q['prompt'],'Question',14,True,keep=True)
            self.bookmark(p,'q_'+str(q['id']))
            p.paragraph_format.space_before=Pt(9);p.paragraph_format.keep_together=True
            for j in [0,2]:
                options=letters[j]+'  '+q['options'][j]+'       '+letters[j+1]+'  '+q['options'][j+1]
                p=self.para(options,'Option',13,keep=(j==0))
                p.paragraph_format.right_indent=Cm(.4);p.paragraph_format.keep_together=True
        self.heading('صَحٌّ أَوْ خَطَأٌ',page=True)
        for index,q in enumerate(q for q in self.data['questions'] if q['type']=='tf'):
            if index and index%10==0:self.heading('صَحٌّ أَوْ خَطَأٌ تَابِعٌ',2,page=True)
            p=self.para(ar(q['id'])+'  '+q['prompt'],'Question',13.5,keep=True)
            self.bookmark(p,'q_'+str(q['id']))
            p.paragraph_format.space_before=Pt(6);p.paragraph_format.keep_together=True
            self.para('صَحٌّ  ☐        خَطَأٌ  ☐','Option',12.5)

        self.heading('مِفْتَاحُ الْإِجَابَةِ',page=True,anchor='answers')
        self.para('لِلْمُرَاجَعَةِ بَعْدَ الْإِجَابَةِ.','Small')
        for typ,title in [('mcq','إِجَابَاتُ الِاخْتِيَارِ مِنْ مُتَعَدِّدٍ'),('tf','إِجَابَاتُ الصَّحِّ وَالْخَطَإِ')]:
            self.heading(title,2,page=(typ=='tf'))
            for q in (q for q in self.data['questions'] if q['type']==typ):
                answer=letters[q['answer']] if typ=='mcq' else ('صَحٌّ' if q['answer'] else 'خَطَأٌ')
                p=self.para(ar(q['id'])+'  '+answer,'Answer',13,True,color='green',keep=True)
                self.bookmark(p,'answer_'+str(q['id']))
                p.paragraph_format.space_before=Pt(4);p.paragraph_format.space_after=Pt(1)
                p=self.para(q['explanation']+'  الْمَوْضِعُ: '+q['reference']+'.','Answer',12.5)
                p.paragraph_format.keep_together=True
        self.heading('الْمَصْدَرُ وَالتَّوْثِيقُ',page=True,anchor='sources')
        for source in self.data['sources']:
            if source.get('bibliography'):self.para(source['bibliography'])
            if source.get('url'):self.hyperlink(source['label'],source['url'])
            else:self.para(source['label'])
        self.doc.core_properties.title=self.data['program_name']+' '+self.data['course_title']
        self.doc.core_properties.author=self.data['program_name']
        self.doc.core_properties.subject='تفسير السعدي مقرر مشكول مع أسئلة وإجابات'
        self.doc.core_properties.comments=''
        return self.doc

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('data',type=Path)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--font',default='Noto Naskh Arabic')
    args=parser.parse_args()
    data=json.loads(args.data.read_text(encoding='utf-8-sig'))
    result=validate(data)
    if not result['ok']:
        print(json.dumps(result,ensure_ascii=False,indent=2));raise SystemExit(1)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    Builder(data,args.font).build().save(args.output)
    print(args.output.resolve())

if __name__=='__main__':main()
