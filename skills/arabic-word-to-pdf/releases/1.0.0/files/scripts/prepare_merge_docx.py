"""Give a DOCX's styles unique names before Word inserts it into another DOCX.

The output is an intermediate copy. Never use it to replace the user's document.
"""

import argparse
import re
import zipfile
from lxml import etree

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
Q = lambda name: f"{{{W}}}{name}"
STYLE_REFS = {"pStyle", "rStyle", "tblStyle", "basedOn", "next", "link", "numStyleLink", "styleLink"}


def prepare(source: str, target: str, prefix: str) -> None:
    with zipfile.ZipFile(source) as src:
        styles = etree.fromstring(src.read("word/styles.xml"))
        mapping = {s.get(Q("styleId")): prefix + s.get(Q("styleId"))
                   for s in styles.findall(Q("style")) if s.get(Q("styleId"))}
        for style in styles.findall(Q("style")):
            old = style.get(Q("styleId"))
            if old in mapping:
                style.set(Q("styleId"), mapping[old])
                name = style.find(Q("name"))
                if name is not None:
                    name.set(Q("val"), prefix + name.get(Q("val"), old))
                if style.get(Q("default")) == "1":
                    style.attrib.pop(Q("default"))
        with zipfile.ZipFile(target, "w") as dst:
            for item in src.infolist():
                raw = src.read(item.filename)
                if item.filename.startswith("word/") and item.filename.endswith(".xml"):
                    root = styles if item.filename == "word/styles.xml" else etree.fromstring(raw)
                    for elem in root.iter():
                        if etree.QName(elem).namespace == W and etree.QName(elem).localname in STYLE_REFS:
                            old = elem.get(Q("val"))
                            if old in mapping:
                                elem.set(Q("val"), mapping[old])
                    if item.filename.startswith(("word/document.xml", "word/header", "word/footer", "word/footnotes", "word/endnotes")):
                        for p in root.iter(Q("p")):
                            ppr = p.find(Q("pPr"))
                            if ppr is None:
                                ppr = etree.Element(Q("pPr"))
                                p.insert(0, ppr)
                            if ppr.find(Q("pStyle")) is None and "Normal" in mapping:
                                ps = etree.Element(Q("pStyle"))
                                ps.set(Q("val"), mapping["Normal"])
                                ppr.insert(0, ps)
                    raw = etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone=True)
                dst.writestr(item, raw)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("source")
    ap.add_argument("target")
    ap.add_argument("prefix")
    args = ap.parse_args()
    if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{0,24}_", args.prefix):
        ap.error("prefix must be an ASCII style prefix ending in underscore")
    prepare(args.source, args.target, args.prefix)
