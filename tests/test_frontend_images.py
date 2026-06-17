import logging
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock


class FrontendImageRenderingTests(unittest.TestCase):
    def test_app_configures_parser_info_logging(self):
        import app

        self.assertEqual(logging.getLogger("parser").level, logging.INFO)

    def test_question_detail_modal_renders_images_from_api_response(self):
        path = os.path.join(os.path.dirname(__file__), "..", "static", "app.js")
        with open(path, "r", encoding="utf-8") as f:
            js = f.read()

        self.assertIn("q.images", js)
        self.assertIn("question-images", js)
        self.assertIn("<img", js)

    def test_image_route_serves_persisted_image_files(self):
        import app as app_module
        import config

        with tempfile.TemporaryDirectory() as tmp:
            images_dir = Path(tmp, "images")
            images_dir.mkdir()
            Path(images_dir, "sample.jpg").write_bytes(b"image-bytes")
            with mock.patch.object(config, "DATA_DIR", tmp), \
                 mock.patch.object(app_module, "DATA_DIR", tmp):
                response = app_module.app.test_client().get("/images/sample.jpg")
                status_code = response.status_code
                data = response.data
                response.close()

        self.assertEqual(status_code, 200)
        self.assertEqual(data, b"image-bytes")


if __name__ == "__main__":
    unittest.main()
