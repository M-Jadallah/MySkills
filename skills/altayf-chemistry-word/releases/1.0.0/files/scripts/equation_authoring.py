"""Small native OMML constructor for reviewed formulas and stacked fractions.

Input parts are strings or {"fraction":{"numerator":parts,"denominator":parts}}.
It does not decide which equation is scientifically correct.
"""
import argparse,json
from lxml import etree as E

M='http://schemas.openxmlformats.org/officeDocument/2006/math'
def tag(n):return '{'+M+'}'+n
def _parts(parent,parts):
    if isinstance(parts,(str,int,float)):parts=[str(parts)]
    if not isinstance(parts,list):raise ValueError('Equation parts must be text or a list')
    for part in parts:
        if isinstance(part,str):
            if not part:continue
            run=E.SubElement(parent,tag('r'));E.SubElement(run,tag('t')).text=part
        elif isinstance(part,dict) and set(part)=={'fraction'}:
            frac=part['fraction']
            if set(frac)!={'numerator','denominator'}:raise ValueError('Fraction needs numerator and denominator')
            f=E.SubElement(parent,tag('f'))
            _parts(E.SubElement(f,tag('num')),frac['numerator'])
            _parts(E.SubElement(f,tag('den')),frac['denominator'])
        else:raise ValueError('Unsupported math part; extend and visually test before use')
def equation(parts):
    root=E.Element(tag('oMath'),nsmap={'m':M});_parts(root,parts)
    return E.tostring(root,encoding='unicode')
def main():
    ap=argparse.ArgumentParser();ap.add_argument('spec_json',help='JSON file containing {"parts":[...]}');a=ap.parse_args()
    obj=json.load(open(a.spec_json,encoding='utf-8'))
    print(equation(obj['parts']))
if __name__=='__main__':main()
