import os
import unittest


class AdminUploadDocumentTests(unittest.TestCase):
    def test_upload_template_accepts_pdf_doc_and_docx(self):
        path = os.path.join(os.path.dirname(__file__), "..", "templates", "admin", "upload.html")
        with open(path, "r", encoding="utf-8") as f:
            html = f.read()

        self.assertIn('accept=".pdf,.doc,.docx"', html)
        self.assertIn("fd.append('document', file)", html)


if __name__ == "__main__":
    unittest.main()
