import os
import tempfile
import unittest

import app as gaokao_app
import models


class UITemplateStructureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tempdir = tempfile.TemporaryDirectory()
        cls.original_db_path = models.DB_PATH
        models.DB_PATH = os.path.join(cls.tempdir.name, "test.db")
        models.init_db()

        cls.vip_user_id = models.create_user("vipuser", "secret123")
        cls.admin_user_id = models.create_user("adminuser", "secret123", is_admin=1)

        paper_id = models.insert_paper(2025, "全国卷", "化学", "2025 全国卷 化学")
        models.insert_question(
            paper_id=paper_id,
            year=2025,
            province="全国卷",
            paper_type="化学",
            question_num=1,
            q_type="选择题",
            stem="下列说法正确的是",
            answer="A",
            options='[{"A":"正确","B":"错误"}]',
            explanation="这里是解析",
            topics="氧化还原",
        )

        cls.app = gaokao_app.app
        cls.app.config.update(TESTING=True)

    @classmethod
    def tearDownClass(cls):
        models.DB_PATH = cls.original_db_path
        cls.tempdir.cleanup()

    def login(self, username="vipuser", password="secret123"):
        client = self.app.test_client()
        client.post(
            "/auth/login",
            data={"username": username, "password": password},
            follow_redirects=True,
        )
        return client

    def test_homepage_uses_new_search_shell(self):
        response = self.login().get("/")
        html = response.get_data(as_text=True)

        self.assertEqual(response.status_code, 200)
        self.assertIn("search-shell", html)
        self.assertIn("search-hero", html)
        self.assertIn("results-panel", html)

    def test_auth_pages_use_new_auth_layout(self):
        login_html = self.app.test_client().get("/auth/login").get_data(as_text=True)
        register_html = self.app.test_client().get("/auth/register").get_data(as_text=True)

        self.assertIn("auth-shell", login_html)
        self.assertIn("auth-card", login_html)
        self.assertIn("auth-shell", register_html)
        self.assertIn("auth-card", register_html)

    def test_vip_page_uses_membership_layout(self):
        html = self.login().get("/api/vip/page").get_data(as_text=True)

        self.assertIn("membership-shell", html)
        self.assertIn("benefit-grid", html)
        self.assertIn("activation-panel", html)

    def test_admin_dashboard_uses_workspace_layout(self):
        html = self.login("adminuser", "secret123").get("/admin/", follow_redirects=True).get_data(as_text=True)

        self.assertIn("admin-workspace", html)
        self.assertIn("workspace-header", html)
        self.assertIn("stats-grid", html)

    def test_stylesheet_contains_light_theme_tokens(self):
        css_path = os.path.join(os.path.dirname(__file__), "..", "static", "style.css")
        with open(css_path, "r", encoding="utf-8") as f:
            css = f.read()

        self.assertIn("--page-bg", css)
        self.assertIn("--surface-1", css)
        self.assertIn(".search-hero", css)
        self.assertIn(".admin-workspace", css)


if __name__ == "__main__":
    unittest.main()
