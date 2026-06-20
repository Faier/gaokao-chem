import sys
from parser import extract_text_from_document, extract_docx_embedded_images_as_data_urls
import glob

print("Testing DOCX...")
doc_path = glob.glob(r'D:\Claude\gaokao-chem\data\uploads\*2025*.docx')[0]
text = extract_text_from_document(doc_path)
images = extract_docx_embedded_images_as_data_urls(doc_path)

# Look for [图片] around question 6
q6_idx = text.find('6.  温郁金')
if q6_idx != -1:
    print(text[q6_idx:q6_idx+200])
print(f"Extracted {len(images)} images from docx.")

print("\nTesting PDF...")
# Generate a test PDF with text and images
import fitz
doc = fitz.open()
page = doc.new_page()
page.insert_text((50, 50), "Question 1. Look at this image:")
# Insert an image
pix = fitz.Pixmap(fitz.csRGB, 100, 100)
pix.clear_with(255)
page.insert_image(fitz.Rect(50, 100, 150, 200), pixmap=pix)
page.insert_text((50, 250), "A. True\nB. False")
doc.save("test_gen2.pdf")
doc.close()

from parser import extract_text_from_document, extract_pdf_embedded_images_as_data_urls
pdf_text = extract_text_from_document("test_gen2.pdf")
pdf_images = extract_pdf_embedded_images_as_data_urls("test_gen2.pdf")

print(pdf_text[:300])
print(f"Extracted {len(pdf_images)} images from pdf.")
