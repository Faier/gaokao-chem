import os
import glob
from docx import Document

directory = r'D:\Claude\gaokao-chem\data\uploads'
filepaths = glob.glob(os.path.join(directory, '*2025*.docx'))
if filepaths:
    filepath = filepaths[0]
    doc = Document(filepath)
    with open('output_images.txt', 'w', encoding='utf-8') as f:
        for p in doc.paragraphs:
            text_with_images = []
            for run in p.runs:
                if run.text:
                    text_with_images.append(run.text)
                drawings = run._element.xpath('.//*[local-name()="drawing" or local-name()="pict"]')
                if drawings:
                    text_with_images.append(f"[IMAGE_PLACEHOLDER_{len(drawings)}]")
            text = "".join(text_with_images).strip()
            if '加成产物' in text or '缩聚产物' in text or '温郁金' in text or 'IMAGE' in text:
                f.write(text + '\n')
    print("Done")
