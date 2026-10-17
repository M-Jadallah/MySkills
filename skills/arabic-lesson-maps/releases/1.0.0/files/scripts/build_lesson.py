"""Build the locked Arabic lesson design with genuine editable Word SmartArt.

Requires Python 3.10+, python-docx, lxml. No generative content or diacritics
are invented here: the calling agent supplies linguistically reviewed JSON.
"""
from __future__ import annotations

import argparse
import copy
import json
import re
from io import BytesIO
from pathlib import Path

from docx import Document
from docx.enum.style import WD_STYLE_TYPE
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_CELL_VERTICAL_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Mm, Pt
from lxml import etree
from smartart_backend import materialize

ROOT = Path(__file__).resolve().parents[1]
TOKENS = json.loads((ROOT / 'assets/design-tokens.json').read_text(encoding='utf-8'))
C = TOKENS['colors']
S = TOKENS['sizes_pt']
FONT = TOKENS['font']
PAGE = TOKENS['page']
W = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
CONTENT_WIDTH = (PAGE['width_mm'] - 2*PAGE['margin_mm']) * 72 / 25.4

# Transitional OOXML property order. Keeping properties in schema order avoids
# relying on Word's silent repairs (and preserves repeatable cross-engine layout).
PROPERTY_ORDER = {
    'pPr': 'pStyle keepNext keepLines pageBreakBefore framePr widowControl numPr suppressLineNumbers pBdr shd tabs suppressAutoHyphens kinsoku wordWrap overflowPunct topLinePunct autoSpaceDE autoSpaceDN bidi adjustRightInd snapToGrid spacing ind contextualSpacing mirrorIndents suppressOverlap jc textDirection textAlignment textboxTightWrap outlineLvl divId cnfStyle rPr sectPr pPrChange',
    'rPr': 'rStyle rFonts b bCs i iCs caps smallCaps strike dstrike outline shadow emboss imprint noProof snapToGrid vanish webHidden color spacing w kern position sz szCs highlight u effect bdr shd fitText vertAlign rtl cs em lang eastAsianLayout specVanish oMath rPrChange',
    'tblPr': 'tblStyle tblpPr tblOverlap bidiVisual tblStyleRowBandSize tblStyleColBandSize tblW jc tblCellSpacing tblInd tblBorders shd tblLayout tblCellMar tblLook tblCaption tblDescription tblPrChange',
    'tcPr': 'cnfStyle tcW gridSpan hMerge vMerge tcBorders shd noWrap tcMar textDirection tcFitText vAlign hideMark headers cellIns cellDel cellMerge tcPrChange',
    'trPr': 'cnfStyle divId gridBefore gridAfter wBefore wAfter cantSplit trHeight tblHeader tblCellSpacing jc hidden ins del trPrChange',
    'settings': 'writeProtection view zoom removePersonalInformation removeDateAndTime doNotDisplayPageBoundaries displayBackgroundShape printPostScriptOverText printFractionalCharacterWidth printFormsData embedTrueTypeFonts embedSystemFonts saveSubsetFonts saveFormsData mirrorMargins alignBordersAndEdges bordersDoNotSurroundHeader bordersDoNotSurroundFooter gutterAtTop hideSpellingErrors hideGrammaticalErrors activeWritingStyle proofState formsDesign attachedTemplate linkStyles stylePaneFormatFilter stylePaneSortMethod documentType mailMerge revisionView trackRevisions doNotTrackMoves doNotTrackFormatting documentProtection autoFormatOverride styleLockTheme styleLockQFSet defaultTabStop autoHyphenation consecutiveHyphenLimit hyphenationZone doNotHyphenateCaps showEnvelope summaryLength clickAndTypeStyle defaultTableStyle evenAndOddHeaders bookFoldRevPrinting bookFoldPrinting bookFoldPrintingSheets drawingGridHorizontalSpacing drawingGridVerticalSpacing displayHorizontalDrawingGridEvery displayVerticalDrawingGridEvery doNotUseMarginsForDrawingGridOrigin drawingGridHorizontalOrigin drawingGridVerticalOrigin doNotShadeFormData noPunctuationKerning characterSpacingControl printTwoOnOne strictFirstAndLastChars noLineBreaksAfter noLineBreaksBefore savePreviewPicture doNotValidateAgainstSchema saveInvalidXml ignoreMixedContent alwaysShowPlaceholderText doNotDemarcateInvalidXml saveXmlDataOnly useXSLTWhenSaving saveThroughXslt showXMLTags alwaysMergeEmptyNamespace updateFields hdrShapeDefaults footnotePr endnotePr compat docVars rsids attachedSchema themeFontLang clrSchemeMapping doNotIncludeSubdocsInStats doNotAutoCompressPictures forceUpgrade captions readModeInkLockDown smartTagType shapeDefaults doNotEmbedSmartTags decimalSymbol listSeparator',
    'numbering': 'numPicBullet abstractNum num numIdMacAtCleanup',
    'tblCellMar': 'top start left bottom end right',
    'tcMar': 'top start left bottom end right',
}
PROPERTY_ORDER['settings'] = PROPERTY_ORDER['settings'].replace('rsids attachedSchema', 'rsids mathPr attachedSchema')


def normalize_properties(doc):
    for part in doc.part.package.parts:
        root = getattr(part, 'element', None)
        if root is None:
            continue
        for parent in root.iter():
            if not isinstance(parent.tag, str) or not parent.tag.startswith('{'+W+'}'):
                continue
            kind = etree.QName(parent).localname
            if kind not in PROPERTY_ORDER:
                continue
            order = {name:i for i,name in enumerate(PROPERTY_ORDER[kind].split())}
            if kind in ('pPr','rPr','tblPr','tcPr','trPr'):
                seen = set()
                for child in reversed(list(parent)):
                    if child.tag in seen:
                        parent.remove(child)
                    else:
                        seen.add(child.tag)
            parent[:] = sorted(parent, key=lambda c: order.get(etree.QName(c).localname, 10000))
    zoom = doc.settings.element.find(qn('w:zoom'))
    if zoom is not None and zoom.get(qn('w:percent')) is None:
        zoom.set(qn('w:percent'), '100')




def word_element(parent, local_name, **attrs):
    item = OxmlElement('w:' + local_name)
    for key, val in attrs.items():
        item.set(qn('w:' + key), str(val))
    parent.append(item)
    return item


def font_properties(rpr, size, color=C['ink'], bold=False, italic=False, underline=False):
    for old in list(rpr):
        if old.tag in {qn('w:rFonts'), qn('w:sz'), qn('w:szCs'), qn('w:color'), qn('w:lang'), qn('w:rtl'), qn('w:b'), qn('w:bCs'), qn('w:i'), qn('w:iCs'), qn('w:u')}:
            rpr.remove(old)
    f = word_element(rpr, 'rFonts')
    for slot in ('ascii', 'hAnsi', 'eastAsia', 'cs'):
        f.set(qn('w:' + slot), FONT)
    word_element(rpr, 'sz', val=round(size * 2))
    word_element(rpr, 'szCs', val=round(size * 2))
    word_element(rpr, 'color', val=color)
    word_element(rpr, 'lang', val='ar-SA', bidi='ar-SA')
    word_element(rpr, 'rtl')
    if bold:
        word_element(rpr, 'b')
        word_element(rpr, 'bCs')
    if italic:
        word_element(rpr, 'i')
        word_element(rpr, 'iCs')
    if underline:
        word_element(rpr, 'u', val='single')


def set_run(run, size=S['body'], color=C['ink'], bold=False, italic=False, underline=False):
    font_properties(run._r.get_or_add_rPr(), size, color, bold, italic, underline)


def rtl(paragraph, center=False):
    ppr = paragraph._p.get_or_add_pPr()
    if ppr.find(qn('w:bidi')) is None:
        word_element(ppr, 'bidi')
    paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER if center else WD_ALIGN_PARAGRAPH.RIGHT
    if not center:
        # Logical start avoids physical left/right mirroring in RTL Word layouts.
        ppr.find(qn('w:jc')).set(qn('w:val'), 'start')
    paragraph.paragraph_format.line_spacing = 1.12


def rich(paragraph, value, size=S['body'], color=C['ink'], bold=False):
    spans = [{'text': value}] if isinstance(value, str) else value
    for span in spans:
        run = paragraph.add_run(span['text'])
        set_run(run, size, color, span.get('bold', bold), span.get('italic', False), span.get('underline', False))
    rtl(paragraph)


def text_of(value):
    return value if isinstance(value, str) else ''.join(x['text'] for x in value)


def add_bookmark(paragraph, name, counter):
    mark = re.sub('[^a-zA-Z0-9_]', '_', name)
    a = OxmlElement('w:bookmarkStart')
    a.set(qn('w:id'), str(counter))
    a.set(qn('w:name'), 'lm_' + mark)
    paragraph._p.insert(1 if paragraph._p.find(qn('w:pPr')) is not None else 0, a)
    z = OxmlElement('w:bookmarkEnd')
    z.set(qn('w:id'), str(counter))
    paragraph._p.append(z)






def add_frame(section):
    header = section.header
    p = header.paragraphs[0]
    p.clear()
    rtl(p, center=True)
    p.paragraph_format.space_after = Pt(0)
    width = PAGE['width_mm'] * 72 / 25.4
    height = PAGE['height_mm'] * 72 / 25.4
    frame = TOKENS['frame']
    # The border has no text: a deterministic high-resolution transparent graphic
    # keeps the exact double-color frame consistent in Word and LibreOffice.
    from PIL import Image, ImageDraw
    scale = 300 / 72
    frame_image = Image.new('RGBA', (round(width*scale), round(height*scale)), (255,255,255,0))
    pen = ImageDraw.Draw(frame_image)
    for name, inset, color, weight in [('outer', frame['outer_inset_pt'], C['primary'], frame['outer_weight_pt']), ('inner', frame['inner_inset_pt'], C['accent'], frame['inner_weight_pt'])]:
        pen.rectangle((round(inset*scale), round(inset*scale), round((width-inset)*scale), round((height-inset)*scale)), outline='#'+color, width=max(1, round(weight*scale)))
    inset = frame['inner_inset_pt']
    for i, (x, y) in enumerate([(inset-2, inset-2), (width-inset-3, inset-2), (inset-2, height-inset-3), (width-inset-3, height-inset-3)]):
        pen.rectangle((round(x*scale), round(y*scale), round((x+5)*scale), round((y+5)*scale)), outline='#'+C['accent'], width=max(1, round(.65*scale)))
    stream = BytesIO()
    frame_image.save(stream, format='PNG')
    stream.seek(0)
    picture = p.add_run().add_picture(stream, width=Mm(PAGE['width_mm']), height=Mm(PAGE['height_mm']))
    inline = picture._inline
    anchor = OxmlElement('wp:anchor')
    for key, val in {'distT':'0','distB':'0','distL':'0','distR':'0','simplePos':'0','relativeHeight':'0','behindDoc':'1','locked':'1','layoutInCell':'1','allowOverlap':'1'}.items():
        anchor.set(key, val)
    pos = OxmlElement('wp:simplePos')
    pos.set('x','0'); pos.set('y','0'); anchor.append(pos)
    for axis in ('H', 'V'):
        pos = OxmlElement('wp:position'+axis)
        pos.set('relativeFrom', 'page')
        off = OxmlElement('wp:posOffset'); off.text = '0'; pos.append(off); anchor.append(pos)
    anchor.append(copy.deepcopy(inline.find(qn('wp:extent'))))
    anchor.append(OxmlElement('wp:wrapNone'))
    for tag in ('wp:docPr','wp:cNvGraphicFramePr','a:graphic'):
        found = inline.find(qn(tag))
        if found is not None:
            anchor.append(copy.deepcopy(found))
    anchor.find(qn('wp:docPr')).set('name', 'Locked navy gold page frame')
    inline.getparent().replace(inline, anchor)
    run = p.add_run(TOKENS['fixed_labels']['header'])
    set_run(run, S['small'], C['primary'])
    footer = section.footer.paragraphs[0]
    footer.clear()
    rtl(footer, center=True)
    r = footer.add_run()
    set_run(r, S['footer'], C['primary'])
    word_element(r._r, 'fldChar', fldCharType='begin')
    r = footer.add_run()
    set_run(r, S['footer'], C['primary'])
    instr = word_element(r._r, 'instrText')
    instr.set(qn('xml:space'), 'preserve')
    instr.text = ' PAGE \\* Arabic '
    r = footer.add_run()
    set_run(r, S['footer'], C['primary'])
    word_element(r._r, 'fldChar', fldCharType='separate')
    r = footer.add_run('1')
    set_run(r, S['footer'], C['primary'])
    r = footer.add_run()
    set_run(r, S['footer'], C['primary'])
    word_element(r._r, 'fldChar', fldCharType='end')


def make_template(path):
    doc = Document()
    # Register the requested family in fontTable as well as rFonts; the renderer
    # separately checks the actual exported fonts to detect any substitution.
    font_part = next(p for p in doc.part.package.parts if str(p.partname) == '/word/fontTable.xml')
    fonts = etree.fromstring(font_part.blob)
    if not any(f.get(qn('w:name')) == FONT for f in fonts):
        registered = word_element(fonts, 'font', name=FONT)
        word_element(registered, 'charset', val='B2')
        word_element(registered, 'family', val='roman')
        word_element(registered, 'pitch', val='variable')
    font_part._blob = etree.tostring(fonts, xml_declaration=True, encoding='UTF-8', standalone=True)
    for border in list(doc.styles.element.iter(qn('w:pBdr'))):
        border.getparent().remove(border)
    for style in doc.styles:
        if style.type in (WD_STYLE_TYPE.PARAGRAPH, WD_STYLE_TYPE.CHARACTER, WD_STYLE_TYPE.TABLE):
            rpr = style.element.get_or_add_rPr()
            font_properties(rpr, S['body'])
    style_specs = {'Normal': (S['body'], C['ink'], False), 'Title': (S['title'], C['primary'], True), 'Heading 1': (S['topic'], C['primary'], True), 'Heading 2': (S['section'], C['primary'], True), 'Heading 3': (S['body'], C['secondary'], True), 'Caption': (S['small'], C['secondary'], False)}
    for name, (size, color, bold) in style_specs.items():
        st = doc.styles[name]
        font_properties(st.element.get_or_add_rPr(), size, color, bold)
        st.paragraph_format.line_spacing = 1.12
        st.paragraph_format.space_after = Pt(5)
        st.paragraph_format.space_before = Pt(7 if name.startswith('Heading') else 0)
        word_element(st.element.get_or_add_pPr(), 'bidi')
        st.paragraph_format.keep_with_next = name.startswith('Heading') or name == 'Title'
    defaults = doc.styles.element.find(qn('w:docDefaults'))
    if defaults is not None:
        rpdef = defaults.find(qn('w:rPrDefault'))
        if rpdef is not None:
            rp = rpdef.find(qn('w:rPr'))
            if rp is None:
                rp = word_element(rpdef, 'rPr')
            font_properties(rp, S['body'])
    section = doc.sections[0]
    section.page_width, section.page_height = Mm(PAGE['width_mm']), Mm(PAGE['height_mm'])
    section.left_margin = section.right_margin = Mm(PAGE['margin_mm'])
    section.top_margin, section.bottom_margin = Mm(PAGE['top_mm']), Mm(PAGE['bottom_mm'])
    section.header_distance, section.footer_distance = Mm(7.5), Mm(7.8)
    add_frame(section)
    settings = doc.settings.element
    word_element(settings, 'updateFields', val='true')
    doc.core_properties.title = 'قَالَبُ خَرَائِطِ الدَّرْسِ'
    doc.core_properties.subject = 'Arabic lesson fixed template v1.0'
    path.parent.mkdir(parents=True, exist_ok=True)
    normalize_properties(doc)
    doc.save(path)


def heading(doc, label, level=2):
    p = doc.add_paragraph(style='Heading ' + str(level))
    rich(p, label, S['topic'] if level == 1 else S['section'], C['primary'], True)
    p.paragraph_format.keep_with_next = True
    if level == 2:
        shd = word_element(p._p.get_or_add_pPr(), 'shd', val='clear', fill=C['tint'])
        borders = word_element(p._p.get_or_add_pPr(), 'pBdr')
        word_element(borders, 'bottom', val='single', sz='5', color=C['accent'], space='3')
    return p


def numbering(doc, ordered):
    root = doc.part.numbering_part.element
    ids = [int(x.get(qn('w:abstractNumId'))) for x in root.findall(qn('w:abstractNum'))]
    aid = max(ids, default=-1) + 1
    a = word_element(root, 'abstractNum', abstractNumId=aid)
    word_element(a, 'multiLevelType', val='singleLevel')
    level = word_element(a, 'lvl', ilvl=0)
    word_element(level, 'start', val=1)
    word_element(level, 'numFmt', val='decimal' if ordered else 'bullet')
    word_element(level, 'lvlText', val='%1.' if ordered else '•')
    word_element(level, 'lvlJc', val='right')
    pp = word_element(level, 'pPr')
    word_element(pp, 'ind', start='370', hanging='270')
    rp = word_element(level, 'rPr')
    font_properties(rp, S['body'])
    nid = max([int(x.get(qn('w:numId'))) for x in root.findall(qn('w:num'))], default=0) + 1
    n = word_element(root, 'num', numId=nid)
    word_element(n, 'abstractNumId', val=aid)
    return nid


def add_text(doc, value, kind='paragraph', num_id=None, bold=False):
    p = doc.add_paragraph()
    rich(p, value, bold=bold)
    p.paragraph_format.space_after = Pt(4)
    p.paragraph_format.widow_control = True
    if kind in ('bullet', 'number'):
        if num_id is None:
            num_id = numbering(doc, kind == 'number')
        np = word_element(p._p.get_or_add_pPr(), 'numPr')
        word_element(np, 'ilvl', val='0')
        word_element(np, 'numId', val=num_id)
    return p


def leaves(node):
    return sum(leaves(c) for c in node.get('children', [])) or 1


def depth(node):
    return 1 + max([depth(c) for c in node.get('children', [])], default=0)


def prune(node, levels, pending):
    out = {k: v for k, v in node.items() if k != 'children'}
    kids = node.get('children', [])
    if kids and levels == 1:
        pending.append(node)
        out['_continued'] = True
    elif kids:
        out['children'] = [prune(c, levels - 1, pending) for c in kids]
    return out


def split_tree(root):
    limit = TOKENS['diagram']['max_leaf_columns']
    queue, panels = [root], []
    while queue:
        node = queue.pop(0)
        kids = node.get('children', [])
        if len(kids) > limit:
            chunks = [kids[i:i + limit] for i in range(0, len(kids), limit)]
            for chunk in chunks:
                q = dict(node)
                q['children'] = chunk
                pending = []
                p = prune(q, 2, pending)
                panels.append(p)
                queue.extend(pending)
            continue
        levels = min(depth(node), TOKENS['diagram']['max_display_levels'])
        while True:
            pending = []
            panel = prune(node, levels, pending)
            if leaves(panel) <= limit or levels <= 2:
                break
            levels -= 1
        panels.append(panel)
        queue.extend(pending)
    return panels














def add_table(doc, block):
    cols = block['columns']
    weights = block.get('widths', [1] * len(cols))
    total = sum(weights)
    widths = [CONTENT_WIDTH * x / total for x in weights]
    table = doc.add_table(rows=1, cols=len(cols))
    table.autofit = False
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    pr = table._tbl.tblPr
    word_element(pr, 'bidiVisual')
    word_element(pr, 'tblLayout', type='fixed')
    existing = pr.find(qn('w:tblW'))
    existing.set(qn('w:type'), 'dxa')
    existing.set(qn('w:w'), str(round(CONTENT_WIDTH*20)))
    for col, w in zip(table.columns, widths):
        col.width = Pt(w)
    borders = word_element(pr, 'tblBorders')
    for side in ('top', 'left', 'bottom', 'right', 'insideH', 'insideV'):
        word_element(borders, side, val='single', sz='5', color=C['line'])
    margin = word_element(pr, 'tblCellMar')
    for side in ('top', 'bottom'):
        word_element(margin, side, w='65', type='dxa')
    for side in ('start', 'end'):
        word_element(margin, side, w='100', type='dxa')
    for rowno, values in enumerate([cols] + block['rows']):
        row = table.rows[0] if rowno == 0 else table.add_row()
        if rowno == 0:
            word_element(row._tr.get_or_add_trPr(), 'tblHeader')
        for cell, width, value in zip(row.cells, widths, values):
            cell.width = Pt(width)
            cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
            word_element(cell._tc.get_or_add_tcPr(), 'shd', val='clear', fill=C['primary'] if rowno == 0 else C['tint'] if rowno % 2 == 0 else C['white'])
            p = cell.paragraphs[0]
            rich(p, value, S['table'], C['white'] if rowno == 0 else C['ink'], rowno == 0)
            p.paragraph_format.space_after = Pt(0)
            p.paragraph_format.keep_with_next = rowno == 0
    after = doc.add_paragraph()
    after.paragraph_format.space_after = Pt(2)
    after.paragraph_format.space_before = Pt(0)
    set_run(after.add_run(), 2)


def plan_diagram(block):
    kind=block.get('kind','tree')
    flat=kind in ('sequence','cycle')
    closing=kind=='cycle' and len(block['nodes'])>6
    if kind=='cycle' and not closing:
        plans=[{'nodes':block['nodes']}]
    elif flat:
        items=block['nodes']+([copy.deepcopy(block['nodes'][0])] if closing else [])
        plans=[];start=0
        while start<len(items):
            plans.append({'nodes':items[start:start+4]})
            if start+4>=len(items):break
            start+=3
    else:
        plans=[{'root':node} for node in split_tree(block['root'])]
    effective='sequence' if closing else kind
    jobs=[]
    for i, plan in enumerate(plans):
        ident=block['id']+'_'+str(i+1)
        if flat:height=250 if effective=='cycle' else min(340,max(150,len(plan['nodes'])*63))
        else:height=min(TOKENS['diagram']['max_height_pt'],max(140,depth(plan['root'])*71+16))
        jobs.append(dict(plan,id=ident,kind=effective,layout_id=TOKENS['smartart']['layouts'][effective],width_pt=CONTENT_WIDTH if not flat or effective=='cycle' else min(CONTENT_WIDTH,410),height_pt=height))
    return jobs


def render_diagram(doc, block, jobs):
    plans=plan_diagram(block)
    for i, panel in enumerate(plans):
        if len(plans)>1:
            p=doc.add_paragraph(style='Caption')
            rich(p,f"{TOKENS['fixed_labels']['part']} {i+1} مِنْ {len(plans)}",S['small'],C['secondary'])
            p.paragraph_format.keep_with_next=True
        p=doc.add_paragraph()
        rtl(p,center=True)
        p.paragraph_format.keep_together=True
        p.paragraph_format.space_before=Pt(7)
        p.paragraph_format.space_after=Pt(9)
        set_run(p.add_run('[[SMARTART:'+panel['id']+']]'),S['body'])
        jobs.append(panel)
    if block.get('kind')=='cycle' and len(block['nodes'])>6:
        p=doc.add_paragraph(style='Caption')
        rich(p,'يَعُودُ آخِرُ التَّسَلْسُلِ إِلَى أَوَّلِهِ.',S['small'],C['secondary'])




def check_content(data):
    if not data.get('title') or not data.get('topics') or not data.get('summary'):
        raise ValueError('title, nonempty topics, and nonempty summary are required')
    seen = set()
    def unique(obj):
        ident = obj['id']
        if not re.fullmatch('[A-Za-z][A-Za-z0-9_-]*', ident):
            raise ValueError('IDs must start with a Latin letter and contain letters, digits, _ or -')
        if ident in seen:
            raise ValueError('Duplicate content ID: ' + ident)
        seen.add(ident)
    def tree(n, active=None):
        if not n.get('label'):
            raise ValueError('Every map node needs a nonempty label')
        for c in n.get('children', []):
            tree(c)
    for topic in data['topics']:
        unique(topic)
        if not topic.get('blocks'):
            raise ValueError('Every topic needs at least one visual block')
        visual = False
        for block in topic['blocks']:
            unique(block)
            typ = block['type']
            if typ == 'diagram':
                visual = True
                kind = block.get('kind', 'tree')
                if kind in ('tree', 'decision'):
                    tree(block['root'])
                elif kind in ('sequence', 'cycle'):
                    if not block.get('nodes'):
                        raise ValueError('A sequence/cycle needs nodes')
                    for n in block['nodes']:
                        tree(n)
                        if n.get('children'):
                            raise ValueError('Sequence/cycle nodes cannot hide children; use a tree or a separate visual block')
                        if kind == 'cycle' and n.get('relation'):
                            raise ValueError('Cycle relations must be represented in an accompanying table, not silently ignored')
                    if kind == 'sequence' and block['nodes'][0].get('relation'):
                        raise ValueError('The first sequence node has no incoming relation')
                else:
                    raise ValueError('Unknown diagram kind: ' + kind)
            elif typ == 'table':
                visual = True
                cols = block['columns']
                if len(cols) < 2 or not block.get('rows'):
                    raise ValueError('A table needs at least 2 columns and nonempty rows')
                if any(len(row) != len(cols) for row in block['rows']):
                    raise ValueError('Table row/column mismatch')
                weights = block.get('widths', [1]*len(cols))
                if len(weights) != len(cols) or any(x <= 0 for x in weights):
                    raise ValueError('Table widths must be positive and match columns')
            elif typ not in ('paragraph', 'quote', 'note'):
                raise ValueError('Unknown block type: ' + typ)
        if not visual:
            raise ValueError('A topic cannot consist only of prose')
    for item in data['summary']:
        unique(item)
        if item.get('kind', 'bullet') not in ('bullet', 'number', 'paragraph', 'heading'):
            raise ValueError('Invalid summary kind')
    return seen


def build(data, out, work_dir=None):
    check_content(data)
    template = ROOT / 'assets/lesson-template.docx'
    if not template.is_file():
        raise FileNotFoundError('The fixed template is missing. Restore the packaged template; do not invent a new theme.')
    doc = Document(template)
    body = doc.element.body
    for node in list(body):
        if node.tag != qn('w:sectPr'):
            body.remove(node)
    counter = 1
    smartart_jobs = []
    title = doc.add_paragraph(style='Title')
    rich(title, data['title'], S['title'], C['primary'], True)
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    if data.get('scope'):
        p = add_text(doc, data['scope'])
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    for topic in data['topics']:
        p = heading(doc, topic['title'], 1)
        add_bookmark(p, topic['id'], counter)
        counter += 1
        for block in topic['blocks']:
            if block.get('title'):
                p = heading(doc, block['title'])
            else:
                p = doc.add_paragraph()
                p.paragraph_format.space_after = Pt(0)
                set_run(p.add_run(), 2)
                p.paragraph_format.keep_with_next = True
            add_bookmark(p, block['id'], counter)
            counter += 1
            typ = block['type']
            if typ == 'diagram':
                render_diagram(doc, block, smartart_jobs)
            elif typ == 'table':
                add_table(doc, block)
            else:
                p = add_text(doc, block['text'])
                if typ == 'note':
                    ppr = p._p.get_or_add_pPr()
                    word_element(ppr, 'shd', fill=C['note'], val='clear')
                    border = word_element(ppr, 'pBdr')
                    for side in ('top', 'left', 'bottom', 'right'):
                        word_element(border, side, val='single', sz='5', color=C['accent'], space='5')
    p = heading(doc, TOKENS['fixed_labels']['summary'], 1)
    p.paragraph_format.page_break_before = True
    current_num, current_kind = None, None
    for item in data['summary']:
        kind = item.get('kind', 'bullet')
        if kind == 'heading':
            p = heading(doc, text_of(item['text']), 2)
            current_num, current_kind = None, None
        else:
            if kind in ('bullet', 'number') and (kind != current_kind or item.get('restart', False)):
                current_num = numbering(doc, kind == 'number')
            p = add_text(doc, item['text'], kind, current_num)
            current_kind = kind
        add_bookmark(p, item['id'], counter)
        counter += 1
    doc.core_properties.title = data['title']
    doc.core_properties.subject = 'Arabic lesson maps / fixed template v2.0 / native SmartArt'
    out.parent.mkdir(parents=True, exist_ok=True)
    normalize_properties(doc)
    materialize(doc, smartart_jobs, out, TOKENS, work_dir)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--content', type=Path)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--make-template', action='store_true')
    parser.add_argument('--work-dir', type=Path)
    args = parser.parse_args()
    if args.make_template:
        make_template(args.output or ROOT / 'assets/lesson-template.docx')
    else:
        if not args.content or not args.output:
            parser.error('--content and --output are required')
        build(json.loads(args.content.read_text(encoding='utf-8-sig')), args.output, args.work_dir)
    print(json.dumps({'output': str((args.output or ROOT / 'assets/lesson-template.docx').resolve())}, ensure_ascii=True))


if __name__ == '__main__':
    main()
