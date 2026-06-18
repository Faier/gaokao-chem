import os
import unittest
from concurrent.futures import ThreadPoolExecutor

import admin_bp


class AdminUploadDocumentTests(unittest.TestCase):
    def test_upload_template_accepts_pdf_doc_and_docx(self):
        path = os.path.join(os.path.dirname(__file__), "..", "templates", "admin", "upload.html")
        with open(path, "r", encoding="utf-8") as f:
            html = f.read()

        self.assertIn('accept=".pdf,.doc,.docx"', html)
        self.assertIn("fd.append('document', file)", html)


class AdminReviewTemplateTests(unittest.TestCase):
    def test_review_template_preserves_image_refs_on_confirm(self):
        path = os.path.join(os.path.dirname(__file__), "..", "templates", "admin", "review.html")
        with open(path, "r", encoding="utf-8") as f:
            html = f.read()

        self.assertIn('name="image_refs"', html)
        self.assertIn("JSON.parse(el.value)", html)
        self.assertIn("q.image_refs", html)


class AdminParseExecutorTests(unittest.TestCase):
    def tearDown(self):
        admin_bp.executor.shutdown(wait=False, cancel_futures=True)
        admin_bp.executor = ThreadPoolExecutor(max_workers=4)

    def test_submit_parse_task_recreates_shutdown_executor(self):
        original = admin_bp.executor
        original.shutdown(wait=False, cancel_futures=True)

        future = admin_bp.submit_parse_task(lambda: "ok")

        self.assertEqual(future.result(timeout=1), "ok")
        self.assertIsNot(admin_bp.executor, original)
if __name__ == "__main__":
    unittest.main()
