"""Compare rendered Word content and every SmartArt part to the input plan."""
from __future__ import annotations

import re
import zipfile
from collections import Counter
from pathlib import Path
from xml.etree import ElementTree as ET

from docx import Document

from . import smartart

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
A = smartart.NS_A
D = smartart.NS_DGM
DSP = "http://schemas.microsoft.com/office/drawing/2008/diagram"


def planned_maps(data: dict) -> list[dict]:
    trees = [data["overview_map"]] if data.get("overview_map") else []

    def visit(node: dict) -> None:
        for child in node.get("subsections", []):
            visit(child)
        if node.get("concept_map"):
            trees.append(node["concept_map"])

    for node in data["sections"]:
        visit(node)
    return trees


def labels(tree) -> list[str]:
    if isinstance(tree, str):
        return [tree]
    return [tree["label"]] + [label for child in tree.get("children", []) for label in labels(child)]


def planned_evidence(data: dict) -> list[dict]:
    out: list[dict] = []

    def visit(node: dict):
        out.extend(b for b in node.get("blocks", []) if b["type"] == "evidence")
        for sub in node.get("subsections", []):
            visit(sub)

    for section in data["sections"]:
        visit(section)
    if data.get("closing"):
        visit(data["closing"])
    return out


def validate_docx(path: str | Path, data: dict) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    try:
        doc = Document(path)
        heads = [p for p in doc.paragraphs if p.style.name.startswith("Heading ")]
        if not heads or heads[0].style.name != "Heading 1" or sum(p.style.name == "Heading 1" for p in heads) != 1:
            errors.append("يجب أن يبدأ المخطط بعنوان واحد من Heading 1")
        if data.get("closing") and (not heads or heads[-1].text != data["closing"]["heading"]):
            errors.append("يجب أن تكون الخاتمة آخر عنوان في الدرس")
        with zipfile.ZipFile(path) as zf:
            names = set(zf.namelist())
            for name in names:
                if name.endswith(".xml") or name.endswith(".rels"):
                    ET.fromstring(zf.read(name))
            root = ET.fromstring(zf.read("word/document.xml"))
            xml = zf.read("word/document.xml").decode("utf-8")
            if smartart.PLACEHOLDER_PREFIX in xml:
                errors.append("بقي موضع خريطة غير مولد")
            if any(name.startswith("word/media/") for name in names):
                errors.append("الخرائط يجب أن تكون SmartArt دون صور")
            maps = planned_maps(data)
            actual_parts = [name for name in names if re.fullmatch(r"word/diagrams/data\d+\.xml", name)]
            if len(actual_parts) != len(maps):
                errors.append("عدد أجزاء الخرائط لا يطابق خطة الدرس")
            if maps:
                sa_errors, sa_warnings = smartart.validate_smartart_docx(path)
                errors.extend(sa_errors)
                warnings.extend(sa_warnings)
            for i, tree in enumerate(maps, 1):
                for kind in ("data", "layout", "colors", "quickStyle", "drawing"):
                    if f"word/diagrams/{kind}{i}.xml" not in names:
                        errors.append(f"الخريطة {i}: جزء مفقود {kind}")
                if f"word/diagrams/data{i}.xml" not in names or f"word/diagrams/drawing{i}.xml" not in names:
                    continue
                model = ET.fromstring(zf.read(f"word/diagrams/data{i}.xml"))
                cached = ET.fromstring(zf.read(f"word/diagrams/drawing{i}.xml"))
                expected = Counter(labels(tree))
                actual = Counter(t.text or "" for t in model.findall(f".//{{{A}}}t"))
                shown = Counter(t.text or "" for t in cached.findall(f".//{{{A}}}t"))
                if actual != expected or shown != expected:
                    errors.append(f"الخريطة {i}: نص العقد في البيانات أو المعاينة لا يطابق المدخل")
                data_ids = {p.get("modelId") for p in model.findall(f"{{{D}}}ptLst/{{{D}}}pt") if p.get("type") is None}
                drawing_ids = {p.get("modelId") for p in cached.findall(f".//{{{DSP}}}sp") if p.find(f"{{{DSP}}}txBody") is not None}
                if data_ids != drawing_ids:
                    errors.append(f"الخريطة {i}: معرفات عقد الرسم غير متصلة ببيانات SmartArt")
                if f"word/diagrams/_rels/data{i}.xml.rels" not in names:
                    errors.append(f"الخريطة {i}: رابط المعاينة المخبأة مفقود")
            boxes = []
            for table in root.findall(f".//{{{W}}}tbl"):
                cells = table.findall(f"{{{W}}}tr/{{{W}}}tc")
                if len(cells) == 1 and cells[0].find(f"{{{W}}}tcPr/{{{W}}}shd") is not None:
                    fill = cells[0].find(f"{{{W}}}tcPr/{{{W}}}shd").get(f"{{{W}}}fill")
                    if fill == "EAF5F0":
                        boxes.append(cells[0])
            evidence = planned_evidence(data)
            if len(boxes) != len(evidence):
                errors.append("عدد صناديق الأدلة لا يطابق المدخل")
            for index, (cell, block) in enumerate(zip(boxes, evidence), 1):
                paragraph = cell.find(f"{{{W}}}p")
                literal = "".join(t.text or "" for t in paragraph.findall(f".//{{{W}}}t")) if paragraph is not None else ""
                # Newlines are w:br nodes; compare the text without line separators.
                if literal != block["text"].replace("\r", "").replace("\n", ""):
                    errors.append(f"الدليل {index}: تغير النص المنقول عند البناء")
            if data.get("closing"):
                rels = ET.fromstring(zf.read("word/_rels/document.xml.rels"))
                targets = {r.get("Target") for r in rels if r.get("TargetMode") == "External"}
                sources = {s["id"]: s for s in data["sources"]}
                for sid in data["closing"]["verification"]["source_ids"]:
                    source = sources[sid]
                    if source.get("url") and source["url"] not in targets:
                        errors.append(f"رابط مصدر الخاتمة غير محفوظ حرفيًا: {sid}")
    except Exception as exc:
        errors.append(f"تعذّر فحص Word: {exc}")
    return errors, warnings
