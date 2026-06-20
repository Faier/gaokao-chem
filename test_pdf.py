import fitz

filepath = r'D:\Claude\gaokao-chem\test.pdf'
try:
    doc = fitz.open(filepath)
    for page in doc:
        blocks = page.get_text("dict")["blocks"]
        for b in blocks:
            if b['type'] == 0:
                # Text block
                print("TEXT", b['bbox'])
            elif b['type'] == 1:
                # Image block
                print("IMAGE", b['bbox'])
        break
except Exception as e:
    print(e)
