"""Real Word SmartArt hierarchy with a cache built from each lesson's labels.

The CLI publishes only when every requested map passes validation. Source
templates supply layout and styling; all node text and cached shapes are
generated from the current tree. No image fallback or failure-note delivery.
"""

from __future__ import annotations

import contextlib
import os
import posixpath
import re
import shutil
import uuid
import zipfile
from xml.etree import ElementTree as ET
from pathlib import Path
from typing import Any
from xml.sax.saxutils import escape as xml_escape

from .styles import BLACK, BROWN, GOLD, RED, WHITE

NS_DGM = "http://schemas.openxmlformats.org/drawingml/2006/diagram"
NS_A = "http://schemas.openxmlformats.org/drawingml/2006/main"
NS_R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
NS_WP = "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing"

CT_DGM_DATA = "application/vnd.openxmlformats-officedocument.drawingml.diagramData+xml"
CT_DGM_LAYOUT = "application/vnd.openxmlformats-officedocument.drawingml.diagramLayout+xml"
CT_DGM_STYLE = "application/vnd.openxmlformats-officedocument.drawingml.diagramStyle+xml"
CT_DGM_COLORS = "application/vnd.openxmlformats-officedocument.drawingml.diagramColors+xml"
CT_DGM_DRAWING = "application/vnd.ms-office.drawingml.diagramDrawing+xml"

RT_DGM_DATA = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/diagramData"
RT_DGM_LAYOUT = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/diagramLayout"
RT_DGM_QUICK_STYLE = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/diagramQuickStyle"
RT_DGM_COLORS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/diagramColors"
RT_DGM_DRAWING = "http://schemas.microsoft.com/office/2007/relationships/diagramDrawing"

LAYOUT_URI = "urn:microsoft.com/office/officeart/2005/8/layout/orgChart1"
QS_TYPE_ID = "urn:microsoft.com/office/officeart/2005/8/quickstyle/simple1"
CS_TYPE_ID = "urn:microsoft.com/office/officeart/2005/8/colors/accent1_2"

# Per-depth (fill, text) colors, anchored to the unified brand palette for
# the first two levels (RED / BROWN, matching the Heading 1/3 colors) and
# extended with the study-summary bot's proven lightened gradient for
# deeper levels.
_PASTEL_GOLD = "E8D5A8"
_PASTEL_CREAM = "FFF7E6"
_NAVY_LIGHT = "5A7A9A"
_GREEN_LIGHT = "5A8F7C"

DEPTH_COLORS: list[tuple[str, str]] = [
    (RED, WHITE),
    (BROWN, WHITE),
    (_GREEN_LIGHT, WHITE),
    (_NAVY_LIGHT, WHITE),
    (_PASTEL_GOLD, BLACK),
    (_PASTEL_CREAM, BLACK),
]

FONT_SIZE_HALF_PTS = 1800  # DrawingML uses hundredths of a point: 18pt.
TRADITIONAL_ARABIC = "Traditional Arabic"

_SCRIPT_DIR = Path(__file__).resolve().parent
_TEMPLATE_DIR = _SCRIPT_DIR / "smartart_templates"

PLACEHOLDER_PREFIX = "__SMARTART_PLACEHOLDER_"


class SmartArtError(RuntimeError):
    """Raised when a SmartArt diagram cannot be built or injected.

    Callers must not publish the failed temporary build or substitute images.
    """


def _gid() -> str:
    return "{" + str(uuid.uuid4()).upper() + "}"


def _depth_colors(depth: int) -> tuple[str, str]:
    if depth < len(DEPTH_COLORS):
        return DEPTH_COLORS[depth]
    return DEPTH_COLORS[-1]


# Arabic tashkeel (diacritic) marks are separate Unicode codepoints layered
# onto base letters, so a fully-diacritized label carries roughly 1.5-2x as
# many codepoints per visible word as the same label without diacritics.
# This cap is sized in codepoints, not visible characters, so it's set high
# enough that a diacritized 2-7 word node label (per the AI prompt's own
# guidance) isn't truncated mid-word just because tashkeel doubled its
# codepoint count. Was 80 (undiacritized-only sizing); 160 leaves comfortable
# room while still bounding worst-case diagram shape size.
LABEL_MAX_CODEPOINTS = 160


def _normalize_tree(node: Any, depth: int = 0, max_depth: int = 6) -> dict[str, Any]:
    if isinstance(node, str):
        return {"label": node.strip()[:LABEL_MAX_CODEPOINTS], "children": [], "depth": depth}
    if isinstance(node, dict):
        label = str(
            node.get("label") or node.get("title") or node.get("root") or node.get("center") or ""
        ).strip()[:LABEL_MAX_CODEPOINTS]
        raw_children = node.get("children") or node.get("branches") or []
        children = []
        if depth < max_depth and isinstance(raw_children, list):
            for child in raw_children:
                normed = _normalize_tree(child, depth + 1, max_depth)
                if normed["label"]:
                    children.append(normed)
        return {"label": label, "children": children, "depth": depth}
    return {"label": str(node).strip()[:LABEL_MAX_CODEPOINTS], "children": [], "depth": depth}


def _tree_depth(node: dict[str, Any]) -> int:
    children = node.get("children") or []
    if not children:
        return 0
    return 1 + max(_tree_depth(c) for c in children)


def _leaf_count(node: dict[str, Any]) -> int:
    children = node.get("children") or []
    if not children:
        return 1
    return sum(_leaf_count(c) for c in children)


def _node_count(node: dict[str, Any]) -> int:
    return 1 + sum(_node_count(c) for c in (node.get("children") or []))


# Page is 8.5in x 11in with 0.5in margins on every side (see
# app/docx/styles.py::setup_document), so usable content area is 7.5in x
# 10in = 6858000 x 9144000 EMU. The diagram must never be generated wider
# or taller than that or Word has to clip/force-scale it. MAX_WIDTH_EMU
# keeps a small safety buffer under the usable width; MAX_HEIGHT_EMU (8in)
# already sits comfortably under the 10in usable height budget.
MAX_WIDTH_EMU = 6600000  # ~7.22in, just under the 7.5in usable page width
MAX_HEIGHT_EMU = 7315200  # 8in


def _calc_dimensions(tree: dict[str, Any]) -> tuple[int, int]:
    """Diagram width/height in EMUs, scaled to tree size (base 6.0in x 3.5in, capped to page size)."""
    depth = _tree_depth(tree)
    leaves = max(1, _leaf_count(tree))
    nodes = _node_count(tree)

    base_w = 5486400
    leaf_w = leaves * 250000
    width = max(base_w, min(MAX_WIDTH_EMU, leaf_w + 400000))

    base_h = 1645920
    depth_h = (depth + 1) * 700000
    height = max(base_h, min(MAX_HEIGHT_EMU, depth_h + 400000))

    if nodes > 15:
        height = min(MAX_HEIGHT_EMU, height + 600000)

    return width, height


def _build_data_node(node_id: str, text: str, depth: int, lang: str = "ar-JO") -> str:
    escaped = xml_escape(text)
    fill_color, text_color = _depth_colors(depth)
    font_sz = FONT_SIZE_HALF_PTS

    sp_pr = f'<dgm:spPr><a:solidFill><a:srgbClr val="{fill_color}"/></a:solidFill></dgm:spPr>'
    r_pr = (
        f'<a:rPr lang="{lang}" sz="{font_sz}" dirty="0">'
        f'<a:solidFill><a:srgbClr val="{text_color}"/></a:solidFill>'
        f'<a:latin typeface="{TRADITIONAL_ARABIC}"/>'
        f'<a:cs typeface="{TRADITIONAL_ARABIC}"/>'
        f'</a:rPr>'
    )
    return (
        f'<dgm:pt modelId="{node_id}">'
        f'<dgm:prSet phldrT="[Text]"/>'
        f'{sp_pr}'
        f'<dgm:t><a:bodyPr/><a:lstStyle/>'
        f'<a:p><a:r>{r_pr}<a:t>{escaped}</a:t></a:r>'
        f'<a:endParaRPr lang="en-US"/></a:p>'
        f'</dgm:t>'
        f'</dgm:pt>'
    )


def _build_par_trans(par_id: str) -> str:
    return (
        f'<dgm:pt modelId="{par_id}" type="parTrans">'
        f'<dgm:prSet/><dgm:spPr/>'
        f'<dgm:t><a:bodyPr/><a:lstStyle/><a:p><a:endParaRPr lang="en-US"/></a:p></dgm:t>'
        f'</dgm:pt>'
    )


def _build_sib_trans(sib_id: str) -> str:
    return (
        f'<dgm:pt modelId="{sib_id}" type="sibTrans">'
        f'<dgm:prSet/><dgm:spPr/>'
        f'<dgm:t><a:bodyPr/><a:lstStyle/><a:p><a:endParaRPr lang="en-US"/></a:p></dgm:t>'
        f'</dgm:pt>'
    )


def _build_cxn(src_id: str, dst_id: str, src_ord: int, par_id: str, sib_id: str) -> str:
    return (
        f'<dgm:cxn modelId="{_gid()}" '
        f'srcId="{src_id}" destId="{dst_id}" '
        f'srcOrd="{src_ord}" destOrd="0" '
        f'parTransId="{par_id}" sibTransId="{sib_id}"/>'
    )


def build_data1_xml(tree: dict[str, Any], lang: str = "ar-JO") -> bytes:
    """Build data1.xml from a concept tree ({label, children: [...]})."""
    tree = _normalize_tree(tree, max_depth=6)
    if not tree["label"]:
        tree["label"] = "الموضوع"

    doc_id = _gid()
    doc_pt = (
        f'<dgm:pt modelId="{doc_id}" type="doc">'
        f'<dgm:prSet loTypeId="{LAYOUT_URI}" loCatId="hierarchy" '
        f'qsTypeId="{QS_TYPE_ID}" qsCatId="simple" '
        f'csTypeId="{CS_TYPE_ID}" csCatId="accent1" phldr="1"/>'
        f'<dgm:spPr/>'
        f'<dgm:t><a:bodyPr/><a:lstStyle/><a:p><a:endParaRPr lang="en-US"/></a:p></dgm:t>'
        f'</dgm:pt>'
    )

    pts: list[str] = [doc_pt]
    cxns: list[str] = []

    def walk(node: dict[str, Any], parent_id: str, sib_ord: int, depth: int) -> None:
        node_id = _gid()
        par_id = _gid()
        sib_id = _gid()
        pts.append(_build_data_node(node_id, node["label"], depth, lang=lang))
        pts.append(_build_par_trans(par_id))
        pts.append(_build_sib_trans(sib_id))
        cxns.append(_build_cxn(parent_id, node_id, sib_ord, par_id, sib_id))
        for i, child in enumerate(node.get("children", [])):
            walk(child, node_id, i, depth + 1)

    walk(tree, doc_id, 0, 0)

    parts = [
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
        f'<dgm:dataModel xmlns:dgm="{NS_DGM}" xmlns:a="{NS_A}">',
        '<dgm:ptLst>',
        "".join(pts),
        '</dgm:ptLst>',
        '<dgm:cxnLst>',
        "".join(cxns),
        '</dgm:cxnLst>',
        '<dgm:bg/>',
        '<dgm:whole/>',
        '</dgm:dataModel>',
    ]
    return "".join(parts).encode("utf-8")


def build_colors1_xml() -> bytes:
    xml = f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<dgm:colorsDef xmlns:dgm="{NS_DGM}" xmlns:a="{NS_A}" uniqueId="{CS_TYPE_ID}">
  <dgm:title val=""/>
  <dgm:desc val=""/>
  <dgm:catLst>
    <dgm:cat type="accent1" pri="11200"/>
  </dgm:catLst>
  <dgm:styleLbl name="node0">
    <dgm:fillClrLst meth="repeat"><a:srgbClr val="{RED}"/></dgm:fillClrLst>
    <dgm:linClrLst meth="repeat"><a:srgbClr val="{WHITE}"/></dgm:linClrLst>
    <dgm:effectClrLst/><dgm:txLinClrLst/><dgm:txFillClrLst/><dgm:txEffectClrLst/>
  </dgm:styleLbl>
  <dgm:styleLbl name="node1">
    <dgm:fillClrLst meth="repeat">
      <a:srgbClr val="{BROWN}"/><a:srgbClr val="{_GREEN_LIGHT}"/><a:srgbClr val="{_NAVY_LIGHT}"/>
    </dgm:fillClrLst>
    <dgm:linClrLst meth="repeat"><a:srgbClr val="{WHITE}"/></dgm:linClrLst>
    <dgm:effectClrLst/><dgm:txLinClrLst/><dgm:txFillClrLst/><dgm:txEffectClrLst/>
  </dgm:styleLbl>
  <dgm:styleLbl name="lnNode1">
    <dgm:fillClrLst meth="repeat">
      <a:srgbClr val="{BROWN}"/><a:srgbClr val="{_GREEN_LIGHT}"/><a:srgbClr val="{_NAVY_LIGHT}"/>
    </dgm:fillClrLst>
    <dgm:linClrLst meth="repeat"><a:srgbClr val="{WHITE}"/></dgm:linClrLst>
    <dgm:effectClrLst/><dgm:txLinClrLst/><dgm:txFillClrLst/><dgm:txEffectClrLst/>
  </dgm:styleLbl>
  <dgm:styleLbl name="alignNode1">
    <dgm:fillClrLst meth="repeat"><a:srgbClr val="{_PASTEL_GOLD}"/></dgm:fillClrLst>
    <dgm:linClrLst meth="repeat"><a:srgbClr val="{GOLD}"/></dgm:linClrLst>
    <dgm:effectClrLst/><dgm:txLinClrLst/><dgm:txFillClrLst/><dgm:txEffectClrLst/>
  </dgm:styleLbl>
  <dgm:styleLbl name="vennNode1">
    <dgm:fillClrLst meth="repeat"><a:srgbClr val="{RED}"><a:alpha val="50000"/></a:srgbClr></dgm:fillClrLst>
    <dgm:linClrLst meth="repeat"><a:srgbClr val="{WHITE}"/></dgm:linClrLst>
    <dgm:effectClrLst/><dgm:txLinClrLst/><dgm:txFillClrLst/><dgm:txEffectClrLst/>
  </dgm:styleLbl>
</dgm:colorsDef>'''
    return xml.encode("utf-8")


def build_drawing_xml(tree: dict[str, Any], data_xml: bytes, width: int, height: int) -> bytes:
    """Cache this tree's actual editable shapes, never text from a static template.

    The data model remains Word SmartArt. This cache makes the first preview
    display the lesson's own labels before Word recomputes its hierarchy.
    """
    ns_dsp = "http://schemas.microsoft.com/office/drawing/2008/diagram"
    model = ET.fromstring(data_xml)
    points = [p for p in model.findall(f"{{{NS_DGM}}}ptLst/{{{NS_DGM}}}pt") if p.get("type") is None]
    normed = _normalize_tree(tree)
    flat: list[dict[str, Any]] = []
    cursor = 0

    def place(node: dict, depth: int, parent: int | None = None) -> float:
        nonlocal cursor
        index = len(flat)
        item = {"node": node, "depth": depth, "parent": parent}
        flat.append(item)
        centers = [place(child, depth + 1, index) for child in node["children"]]
        if centers:
            center = sum(centers) / len(centers)
        else:
            center = cursor + 0.5
            cursor += 1
        item["center"] = center
        return center

    place(normed, 0)
    leaves = max(1, cursor)
    max_depth = _tree_depth(normed)
    padding, gap = 60000, 180000
    box_width = min(1900000, (width - 2 * padding) // max(1, leaves) - gap)
    box_height = min(900000, (height - 2 * padding) // (max_depth + 1) - gap)
    if box_width < 650000 or box_height < 400000:
        raise SmartArtError("الخريطة مكتظة؛ وزّع الفروع على خرائط أصغر")
    for index, item in enumerate(flat):
        item["id"] = points[index].get("modelId")
        # First sibling is the rightmost in an Arabic hierarchy.
        center_x = width - padding - int(item["center"] / leaves * (width - 2 * padding))
        item["x"] = max(padding, center_x - box_width // 2)
        item["y"] = padding + item["depth"] * ((height - 2 * padding - box_height) // max(1, max_depth))

    shapes: list[str] = []
    shape_id = 1
    for item in flat:
        parent_index = item["parent"]
        if parent_index is None:
            continue
        parent = flat[parent_index]
        px, py = parent["x"] + box_width // 2, parent["y"] + box_height
        cx, cy = item["x"] + box_width // 2, item["y"]
        left, top = min(px, cx), min(py, cy)
        dx, dy = max(1, abs(cx - px)), max(1, abs(cy - py))
        flip = ' flipH="1"' if cx < px else ""
        shapes.append(
            f'<dsp:sp modelId="{_gid()}"><dsp:nvSpPr><dsp:cNvPr id="{shape_id}" name="Connector {shape_id}"/><dsp:cNvSpPr/></dsp:nvSpPr>'
            f'<dsp:spPr><a:xfrm{flip}><a:off x="{left}" y="{top}"/><a:ext cx="{dx}" cy="{dy}"/></a:xfrm>'
            '<a:prstGeom prst="line"><a:avLst/></a:prstGeom><a:noFill/>'
            f'<a:ln w="16000"><a:solidFill><a:srgbClr val="{BROWN}"/></a:solidFill></a:ln></dsp:spPr></dsp:sp>'
        )
        shape_id += 1
    for item in flat:
        fill, color = _depth_colors(item["depth"])
        label = xml_escape(item["node"]["label"])
        shapes.append(
            f'<dsp:sp modelId="{item["id"]}"><dsp:nvSpPr><dsp:cNvPr id="{shape_id}" name="Node {shape_id}"/><dsp:cNvSpPr/></dsp:nvSpPr>'
            f'<dsp:spPr><a:xfrm><a:off x="{item["x"]}" y="{item["y"]}"/><a:ext cx="{box_width}" cy="{box_height}"/></a:xfrm>'
            '<a:prstGeom prst="roundRect"><a:avLst/></a:prstGeom>'
            f'<a:solidFill><a:srgbClr val="{fill}"/></a:solidFill><a:ln w="12700"><a:solidFill><a:srgbClr val="{WHITE}"/></a:solidFill></a:ln></dsp:spPr>'
            '<dsp:txBody><a:bodyPr wrap="square" lIns="40000" rIns="40000" tIns="20000" bIns="20000" anchor="ctr"><a:spAutoFit/></a:bodyPr><a:lstStyle/>'
            f'<a:p><a:pPr algn="ctr" rtl="1"/><a:r><a:rPr lang="ar-JO" sz="{FONT_SIZE_HALF_PTS}"><a:solidFill><a:srgbClr val="{color}"/></a:solidFill>'
            f'<a:latin typeface="{TRADITIONAL_ARABIC}"/><a:cs typeface="{TRADITIONAL_ARABIC}"/></a:rPr><a:t>{label}</a:t></a:r></a:p></dsp:txBody></dsp:sp>'
        )
        shape_id += 1
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<dsp:drawing xmlns:dsp="{ns_dsp}" xmlns:a="{NS_A}"><dsp:spTree>'
        '<dsp:nvGrpSpPr><dsp:cNvPr id="0" name=""/><dsp:cNvGrpSpPr/></dsp:nvGrpSpPr><dsp:grpSpPr/>'
        + "".join(shapes) + '</dsp:spTree></dsp:drawing>'
    ).encode("utf-8")


def _read_template_part(name: str) -> bytes:
    path = _TEMPLATE_DIR / name
    if not path.exists():
        raise SmartArtError(f"SmartArt template part missing: {path}")
    return path.read_bytes()


def _ensure_compat_mode15(settings_xml: str) -> str:
    if re.search(r'compatibilityMode.*?w:val="15"', settings_xml):
        return settings_xml
    if 'w:name="compatibilityMode"' in settings_xml:
        return re.sub(
            r'(w:compatSetting\s+w:name="compatibilityMode"\s+w:uri="[^"]*"\s+w:val=")\d+(")',
            r'\g<1>15\g<2>',
            settings_xml,
        )
    compat_block = (
        '<w:compat>'
        '<w:compatSetting w:name="compatibilityMode" '
        'w:uri="http://schemas.microsoft.com/office/word" w:val="15"/>'
        '</w:compat>'
    )
    if '<w:compat>' not in settings_xml:
        settings_xml = settings_xml.replace("</w:settings>", compat_block + "</w:settings>")
    return settings_xml


def make_placeholder_paragraph_xml(idx: int) -> str:
    """XML for a hidden placeholder paragraph, replaced by the real SmartArt drawing during injection."""
    marker = f"{PLACEHOLDER_PREFIX}{idx}__"
    return f'<w:p><w:r><w:rPr><w:vanish/></w:rPr><w:t>{marker}</w:t></w:r></w:p>'


def inject_smartart(
    docx_path: str | Path,
    tree: dict[str, Any],
    *,
    lang: str = "ar-JO",
    width_emu: int | None = None,
    height_emu: int | None = None,
    diagram_index: int = 1,
) -> None:
    """Inject a real SmartArt diagram into an existing DOCX file (in place).

    Raises SmartArtError on any failure; publish only a fully validated build.
    """
    docx_path = Path(docx_path)
    idx = diagram_index

    try:
        normed_tree = _normalize_tree(tree, max_depth=6)
        if width_emu is None or height_emu is None:
            auto_w, auto_h = _calc_dimensions(normed_tree)
            width_emu = width_emu or auto_w
            height_emu = height_emu or auto_h

        data_xml = build_data1_xml(tree, lang=lang)
        colors_xml = build_colors1_xml()
        layout_xml = _read_template_part("layout1.xml")
        quickstyle_xml = _read_template_part("quickStyle1.xml")
        drawing_xml = build_drawing_xml(tree, data_xml, width_emu, height_emu)
        # Microsoft ODRAWXML dataModelExt points to the cached drawing via
        # the data part's own relationships, rather than an unrelated template.
        dsp_ns = "http://schemas.microsoft.com/office/drawing/2008/diagram"
        ext = (
            f'<dgm:extLst><a:ext uri="{dsp_ns}"><dsp:dataModelExt xmlns:dsp="{dsp_ns}" '
            f'relId="rId1" minVer="http://schemas.openxmlformats.org/drawingml/2006/diagram"/>'
            '</a:ext></dgm:extLst>'
        )
        data_xml = data_xml.replace(b'</dgm:dataModel>', ext.encode("utf-8") + b'</dgm:dataModel>')
    except SmartArtError:
        raise
    except Exception as exc:  # noqa: BLE001 - surfaced to the caller as SmartArtError
        raise SmartArtError(f"Failed to build SmartArt XML parts: {exc}") from exc

    parts = {
        "data": f"word/diagrams/data{idx}.xml",
        "layout": f"word/diagrams/layout{idx}.xml",
        "quickStyle": f"word/diagrams/quickStyle{idx}.xml",
        "colors": f"word/diagrams/colors{idx}.xml",
        "drawing": f"word/diagrams/drawing{idx}.xml",
    }
    part_content_types = {
        parts["data"]: CT_DGM_DATA,
        parts["layout"]: CT_DGM_LAYOUT,
        parts["quickStyle"]: CT_DGM_STYLE,
        parts["colors"]: CT_DGM_COLORS,
        parts["drawing"]: CT_DGM_DRAWING,
    }
    part_contents = {
        parts["data"]: data_xml,
        parts["layout"]: layout_xml,
        parts["quickStyle"]: quickstyle_xml,
        parts["colors"]: colors_xml,
        parts["drawing"]: drawing_xml,
        f"word/diagrams/_rels/data{idx}.xml.rels": (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            f'<Relationship Id="rId1" Type="{RT_DGM_DRAWING}" Target="drawing{idx}.xml"/>'
            '</Relationships>'
        ).encode("utf-8"),
    }
    rel_defs = [
        ("data", RT_DGM_DATA, f"diagrams/data{idx}.xml"),
        ("layout", RT_DGM_LAYOUT, f"diagrams/layout{idx}.xml"),
        ("quickStyle", RT_DGM_QUICK_STYLE, f"diagrams/quickStyle{idx}.xml"),
        ("colors", RT_DGM_COLORS, f"diagrams/colors{idx}.xml"),
        ("drawing", RT_DGM_DRAWING, f"diagrams/drawing{idx}.xml"),
    ]

    placeholder_marker = f"{PLACEHOLDER_PREFIX}{idx}__"
    tmp_in_path = str(docx_path) + ".smartart_in_tmp"
    tmp_out_path = str(docx_path) + ".smartart_out_tmp"

    try:
        shutil.copy2(docx_path, tmp_in_path)

        max_rid = 0
        with zipfile.ZipFile(tmp_in_path, "r") as zin:
            rels_data = zin.read("word/_rels/document.xml.rels").decode("utf-8")
            for m in re.finditer(r'Id="(rId(\d+))"', rels_data):
                max_rid = max(max_rid, int(m.group(2)))

        rid_map = {}
        for key, _rel_type, _target in rel_defs:
            max_rid += 1
            rid_map[key] = f"rId{max_rid}"

        # Write the modified package to a brand-new file, never touching
        # docx_path in place. If anything below raises, the original file is
        # left completely untouched, so the caller's failure-note fallback
        # can safely operate on a known-good DOCX.
        with zipfile.ZipFile(tmp_in_path, "r") as zin:
            with zipfile.ZipFile(tmp_out_path, "w", zipfile.ZIP_DEFLATED) as zout:
                for item in zin.namelist():
                    raw = zin.read(item)

                    if item == "[Content_Types].xml":
                        ct_str = raw.decode("utf-8")
                        for part_name, ct_type in part_content_types.items():
                            override = f'<Override PartName="/{part_name}" ContentType="{ct_type}"/>'
                            ct_str = ct_str.replace("</Types>", override + "</Types>")
                        raw = ct_str.encode("utf-8")

                    elif item == "word/_rels/document.xml.rels":
                        rels_str = raw.decode("utf-8")
                        for key, rel_type, target in rel_defs:
                            rel_xml = f'<Relationship Id="{rid_map[key]}" Type="{rel_type}" Target="{target}"/>'
                            rels_str = rels_str.replace("</Relationships>", rel_xml + "</Relationships>")
                        raw = rels_str.encode("utf-8")

                    elif item == "word/document.xml":
                        doc_str = raw.decode("utf-8")
                        if placeholder_marker in doc_str:
                            drawing_run = (
                                f'<w:r xmlns:r="{NS_R}" xmlns:wp="{NS_WP}" '
                                f'xmlns:a="{NS_A}" xmlns:dgm="{NS_DGM}">'
                                f'<w:rPr><w:noProof/></w:rPr>'
                                f'<w:drawing>'
                                f'<wp:inline distT="0" distB="0" distL="0" distR="0">'
                                f'<wp:extent cx="{width_emu}" cy="{height_emu}"/>'
                                f'<wp:effectExtent l="0" t="0" r="76200" b="0"/>'
                                f'<wp:docPr id="{idx}" name="Diagram {idx}"/>'
                                f'<wp:cNvGraphicFramePr/>'
                                f'<a:graphic>'
                                f'<a:graphicData uri="{NS_DGM}">'
                                f'<dgm:relIds '
                                f'r:dm="{rid_map["data"]}" r:lo="{rid_map["layout"]}" '
                                f'r:qs="{rid_map["quickStyle"]}" r:cs="{rid_map["colors"]}"/>'
                                f'</a:graphicData>'
                                f'</a:graphic>'
                                f'</wp:inline>'
                                f'</w:drawing>'
                                f'</w:r>'
                            )
                            old_run = f'<w:r><w:rPr><w:vanish/></w:rPr><w:t>{placeholder_marker}</w:t></w:r>'
                            if old_run not in doc_str:
                                raise SmartArtError(
                                    f"Placeholder marker {placeholder_marker!r} found but its run XML did not "
                                    "match the expected shape; refusing to inject to avoid corrupting the document."
                                )
                            doc_str = doc_str.replace(old_run, drawing_run)
                        else:
                            raise SmartArtError(
                                f"Placeholder marker {placeholder_marker!r} not found in document.xml; "
                                "the builder must insert it via make_placeholder_paragraph_xml() before saving."
                            )
                        raw = doc_str.encode("utf-8")

                    elif item == "word/settings.xml":
                        raw = _ensure_compat_mode15(raw.decode("utf-8")).encode("utf-8")

                    zout.writestr(item, raw)

                for part_name, part_content in part_contents.items():
                    zout.writestr(part_name, part_content)

        # Only now, after a fully successful rewrite, replace the original.
        os.replace(tmp_out_path, docx_path)
    except SmartArtError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise SmartArtError(f"Failed to inject SmartArt into DOCX package: {exc}") from exc
    finally:
        with contextlib.suppress(OSError):
            os.remove(tmp_in_path)
        with contextlib.suppress(OSError):
            os.remove(tmp_out_path)


def validate_smartart_docx(docx_path: str | Path) -> tuple[list[str], list[str]]:
    """Structural validation of injected SmartArt. Returns (errors, warnings)."""
    errors: list[str] = []
    warnings: list[str] = []
    docx_path = Path(docx_path)

    try:
        with zipfile.ZipFile(docx_path) as zf:
            names = set(zf.namelist())

            diagram_parts = [n for n in names if n.startswith("word/diagrams/")]
            if not diagram_parts:
                errors.append("No SmartArt parts (word/diagrams/) found in the file.")
                return errors, warnings

            for req in ("data", "layout", "colors", "quickStyle", "drawing"):
                if not any(req in n for n in diagram_parts):
                    errors.append(f"Missing SmartArt part: {req}")

            ct = zf.read("[Content_Types].xml").decode("utf-8")
            for req_ct in (CT_DGM_DATA, CT_DGM_LAYOUT, CT_DGM_STYLE, CT_DGM_COLORS, CT_DGM_DRAWING):
                if req_ct not in ct:
                    errors.append(f"Missing Content Type: {req_ct}")

            rels = zf.read("word/_rels/document.xml.rels").decode("utf-8")
            for req_rt in (RT_DGM_DATA, RT_DGM_LAYOUT, RT_DGM_QUICK_STYLE, RT_DGM_COLORS, RT_DGM_DRAWING):
                if req_rt not in rels:
                    errors.append(f"Missing relationship type: {req_rt.split('/')[-1]}")

            doc = zf.read("word/document.xml").decode("utf-8")
            if "dgm:relIds" not in doc:
                errors.append("No dgm:relIds reference found in document.xml")
            for i in range(1, 10):
                if f"{PLACEHOLDER_PREFIX}{i}__" in doc:
                    errors.append(f"Placeholder {i} was never replaced by SmartArt")

            if "word/settings.xml" in names:
                settings = zf.read("word/settings.xml").decode("utf-8")
                if not re.search(r'compatibilityMode.*?w:val="15"', settings):
                    warnings.append("compatibilityMode is not 15 in settings.xml")

            targets = re.findall(r'Target="([^"]+)"', rels)
            for t in targets:
                if t.startswith("http") or t.startswith("/"):
                    continue
                normalized = posixpath.normpath(posixpath.join("word", t))
                if normalized not in names:
                    errors.append(f"Broken relationship target: {t} -> {normalized}")

            seen_rids = set()
            for rid in re.findall(r'Id="(rId\d+)"', rels):
                if rid in seen_rids:
                    errors.append(f"Duplicate relationship id: {rid}")
                seen_rids.add(rid)

    except zipfile.BadZipFile:
        errors.append("Corrupt DOCX file (invalid ZIP).")
    except Exception as exc:  # noqa: BLE001
        errors.append(f"Validation error: {exc}")

    return errors, warnings
