import sys
from parser import extract_text_from_document, extract_docx_embedded_images_as_data_urls
import glob

print("Testing DOCX...")
doc_path = glob.glob(r'D:\Claude\gaokao-chem\data\uploads\*2025*.docx')[0]
text = extract_text_from_document(doc_path)

if '温郁金' in text:
    q6_idx = text.find('温郁金')
    with open('output_q6.txt', 'w', encoding='utf-8') as f:
        f.write(text[max(0, q6_idx-50):q6_idx+200])
    print("Saved to output_q6.txt")
else:
    print("Not found.")
