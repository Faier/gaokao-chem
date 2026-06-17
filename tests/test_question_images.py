import base64
import json
import os
import tempfile
import unittest
from unittest import mock

from flask import Flask

import admin_bp
import models
import query_bp


class QuestionImagePersistenceTests(unittest.TestCase):
    def setUp(self):
        fd, self.db_path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        self.db_patcher = mock.patch.object(models, "DB_PATH", self.db_path)
        self.db_patcher.start()
        models.init_db()

        self.tmpdir = tempfile.mkdtemp()
        self.data_patcher = mock.patch.object(admin_bp, "DATA_DIR", self.tmpdir)
        self.data_patcher.start()
        self.app = Flask(__name__)

        @self.app.teardown_appcontext
        def close_db(error):
            from flask import g
            db = g.pop("db", None)
            if db is not None:
                db.close()

    def tearDown(self):
        self.data_patcher.stop()
        self.db_patcher.stop()
        if os.path.exists(self.db_path):
            os.remove(self.db_path)
        for root, dirs, files in os.walk(self.tmpdir, topdown=False):
            for name in files:
                os.remove(os.path.join(root, name))
            for name in dirs:
                os.rmdir(os.path.join(root, name))
        os.rmdir(self.tmpdir)

    def test_confirm_questions_saves_and_links_only_referenced_images(self):
        paper_id = models.insert_paper(
            year=2025,
            province="四川",
            paper_type="化学",
            title="2025 四川化学",
            file_path="paper.docx",
        )
        image_payloads = [b"first image", b"second image", b"third image"]
        parsed = {
            "questions": [
                {
                    "question_num": 1,
                    "q_type": "选择题",
                    "stem": "有图题",
                    "options": [],
                    "answer": "A",
                    "explanation": "解析",
                    "topics": "实验",
                    "image_refs": [2, 2, "bad", 99],
                },
                {
                    "question_num": 2,
                    "q_type": "填空题",
                    "stem": "无图题",
                    "options": [],
                    "answer": "H2O",
                    "explanation": "解析",
                    "topics": "物质",
                    "image_refs": [],
                },
            ],
            "images": [
                "data:image/jpeg;base64," + base64.b64encode(payload).decode("ascii")
                for payload in image_payloads
            ],
        }
        conn = models.get_db()
        conn.execute(
            "UPDATE papers SET parse_result=?, status='parsed' WHERE id=?",
            (json.dumps(parsed, ensure_ascii=False), paper_id),
        )
        conn.commit()
        conn.close()

        target = admin_bp.review_confirm
        while hasattr(target, "__wrapped__"):
            target = target.__wrapped__
        with self.app.test_request_context(
            f"/review/{paper_id}/confirm",
            method="POST",
            json={"questions": parsed["questions"]},
        ):
            response = target(paper_id)

        body = response.get_json()
        self.assertTrue(body["ok"])
        questions = models.get_paper_questions(paper_id)
        first_images = models.get_question_images(questions[0]["id"])
        second_images = models.get_question_images(questions[1]["id"])

        self.assertEqual([img["seq"] for img in first_images], [2])
        self.assertEqual(second_images, [])
        self.assertTrue(os.path.exists(first_images[0]["file_path"]))
        with open(first_images[0]["file_path"], "rb") as f:
            self.assertEqual(f.read(), image_payloads[1])

    def test_async_parse_stores_full_result_with_images(self):
        paper_id = models.insert_paper(
            year=2025,
            province="四川",
            paper_type="化学",
            title="2025 四川化学",
            file_path="paper.docx",
        )
        parsed = {
            "questions": [{"question_num": 1, "stem": "有图题", "image_refs": [1]}],
            "images": ["data:image/jpeg;base64,abc"],
            "image_source": "DOCX embedded images",
        }

        with mock.patch.object(admin_bp, "parse_document_to_questions", return_value=parsed):
            admin_bp.async_parse_task(self.app, paper_id, "paper.docx")

        stored = models.get_paper(paper_id)
        self.assertEqual(json.loads(stored["parse_result"]), parsed)
        self.assertEqual(stored["status"], "parsed")

    def test_question_api_returns_associated_image_urls(self):
        paper_id = models.insert_paper(
            year=2025,
            province="四川",
            paper_type="化学",
            title="2025 四川化学",
            file_path="paper.docx",
        )
        question_id = models.insert_question(
            paper_id=paper_id,
            year=2025,
            province="四川",
            paper_type="化学",
            question_num=1,
            q_type="选择题",
            stem="有图题",
            answer="A",
            options="[]",
        )
        image_path = os.path.join(self.tmpdir, "images", f"{paper_id}_2.jpg")
        os.makedirs(os.path.dirname(image_path), exist_ok=True)
        with open(image_path, "wb") as f:
            f.write(b"image")
        models.insert_question_image(question_id, paper_id, 2, image_path)

        target = query_bp.api_question
        while hasattr(target, "__wrapped__"):
            target = target.__wrapped__
        with self.app.test_request_context(f"/api/question/{question_id}"):
            response = target(question_id)

        body = response.get_json()
        self.assertEqual(body["images"], [{"seq": 2, "url": f"/images/{paper_id}_2.jpg"}])


if __name__ == "__main__":
    unittest.main()
