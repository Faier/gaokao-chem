import fitz
import sys

# Generate a small test pdf
doc = fitz.open()
page = doc.new_page()
page.insert_text((50, 50), "Hello World!")
page.insert_text((50, 100), "Another line.")
doc.save("test_gen.pdf")
doc.close()

doc = fitz.open("test_gen.pdf")
page = doc[0]
blocks = page.get_text("dict")["blocks"]
for b in blocks:
    if b["type"] == 0:
        print("TEXT:", b.get("lines")[0]["spans"][0]["text"])
    elif b["type"] == 1:
        print("IMAGE:", len(b.get("image", b"")))
