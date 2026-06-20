import os
import glob
from docx import Document

def extract_paragraph_text(paragraph):
    text_parts = []
    for node in paragraph._element.xpath('.//w:t | .//m:t'):
        if node.text:
            text_parts.append(node.text)
    return "".join(text_parts)

directory = r'D:\Claude\gaokao-chem\data\uploads'
filepaths = glob.glob(os.path.join(directory, '*2025*.docx'))
if filepaths:
    filepath = filepaths[0]
    doc = Document(filepath)
    with open('output_clean.txt', 'w', encoding='utf-8') as f:
        for p in doc.paragraphs:
            text = extract_paragraph_text(p).strip()
            if text:
                f.write(text + '\n')
    print("Done")
