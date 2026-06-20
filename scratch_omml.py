import sys
from docx import Document

doc = Document('d:/Claude/gaokao-chem/test2.docx')
for p in doc.paragraphs:
    if '火箭' in p.text or 'N2H4' in p.text:
        print(repr(p.text))
        print("XML:", p._p.xml[:500])
