import os
import tempfile
import unittest
from unittest import mock

import models


class DeletePaperTests(unittest.TestCase):
    def setUp(self):
        fd, self.db_path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        self._patcher = mock.patch.object(models, "DB_PATH", self.db_path)
        self._patcher.start()
        models.init_db()

        self.tmpdir = tempfile.mkdtemp()
        self.upload_path = os.path.join(self.tmpdir, "paper.pdf")
        with open(self.upload_path, "wb") as f:
            f.write(b"%PDF-1.4 fake")

    def tearDown(self):
        self._patcher.stop()
        os.remove(self.db_path)
        if os.path.exists(self.upload_path):
            os.remove(self.upload_path)
        os.rmdir(self.tmpdir)

    def _insert(self, file_path):
        return models.insert_paper(
            year=2024, province="北京", paper_type="化学",
            title="2024 北京化学", file_path=file_path, file_size=12,
        )

    def test_delete_paper_removes_questions_and_upload_file(self):
        paper_id = self._insert(self.upload_path)
        models.insert_question(
            paper_id=paper_id, year=2024, province="北京", paper_type="化学",
            question_num=1, q_type="选择题", stem="题干", answer="A",
        )

        self.assertTrue(os.path.exists(self.upload_path))
        models.delete_paper(paper_id)

        self.assertIsNone(models.get_paper(paper_id))
        self.assertEqual(models.get_paper_questions(paper_id), [])
        self.assertFalse(os.path.exists(self.upload_path), "源文件应被清理")

    def test_delete_paper_preserves_file_when_other_paper_references_it(self):
        paper_a = self._insert(self.upload_path)
        paper_b = self._insert(self.upload_path)

        models.delete_paper(paper_a)

        self.assertIsNone(models.get_paper(paper_a))
        self.assertIsNotNone(models.get_paper(paper_b))
        self.assertTrue(os.path.exists(self.upload_path), "另一个试卷仍引用，文件保留")

    def test_delete_paper_tolerates_missing_file(self):
        paper_id = self._insert(self.upload_path)
        os.remove(self.upload_path)
        models.delete_paper(paper_id)
        self.assertIsNone(models.get_paper(paper_id))


class PapersListTemplateTests(unittest.TestCase):
    def test_papers_list_shows_delete_button(self):
        path = os.path.join(
            os.path.dirname(__file__), "..", "templates", "admin", "papers.html"
        )
        with open(path, "r", encoding="utf-8") as f:
            html = f.read()

        self.assertIn("delete-paper-btn", html)
        self.assertIn("/admin/review/' + paperId + '/delete", html)


if __name__ == "__main__":
    unittest.main()
