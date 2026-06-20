import zipfile
import re
import glob
import os

directory = r'D:\Claude\gaokao-chem\data\uploads'
filepaths = glob.glob(os.path.join(directory, '*2025*.docx'))
if filepaths:
    filepath = filepaths[0]
    try:
        with zipfile.ZipFile(filepath) as zf:
            document_xml = zf.read("word/document.xml").decode("utf-8", errors="ignore")
            rels = zf.read("word/_rels/document.xml.rels").decode("utf-8", errors="ignore")
            rel_targets = dict(re.findall(r'<Relationship[^>]+Id="([^"]+)"[^>]+Target="media/([^"]+)"', rels))
            
            matches = re.findall(r'<(?:a:blip|v:imagedata)[^>]+(?:r:embed|r:id)="([^"]+)"', document_xml)
            print(f"Found {len(matches)} images in document.xml")
            
            for m in matches:
                print(f"Target: {rel_targets.get(m)}")
    except Exception as e:
        print(e)
