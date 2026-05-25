# Gaokao Chem Apple Google UI Refresh Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refresh the whole Flask UI into a light, polished Google-plus-Apple visual style without changing the core search and admin workflows.

**Architecture:** Keep the existing Flask, Jinja, and vanilla JS structure. Add regression tests for the new layout hooks first, then update shared templates and CSS tokens, and finally align the admin screens to the same visual system.

**Tech Stack:** Flask, Jinja2 templates, vanilla JavaScript, CSS, Python `unittest`

---

### Task 1: Lock The New UI Structure With Tests

**Files:**
- Create: `tests/test_ui_structure.py`
- Modify: `D:\Claude\gaokao-chem\app.py` only if a test hook is absolutely required
- Test: `tests/test_ui_structure.py`

- [ ] **Step 1: Write the failing test**

```python
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
        html = self.login("adminuser", "secret123").get("/admin").get_data(as_text=True)

        self.assertIn("admin-workspace", html)
        self.assertIn("workspace-header", html)
        self.assertIn("stats-grid", html)

    def test_stylesheet_contains_light_theme_tokens(self):
        with open("static/style.css", "r", encoding="utf-8") as f:
            css = f.read()

        self.assertIn("--page-bg", css)
        self.assertIn("--surface-1", css)
        self.assertIn(".search-hero", css)
        self.assertIn(".admin-workspace", css)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest -v tests.test_ui_structure`
Expected: `FAIL` because the new layout classes and light-theme tokens do not exist yet.

- [ ] **Step 3: Write minimal implementation**

```html
<section class="search-shell">
  <header class="search-hero"></header>
  <section class="results-panel"></section>
</section>
```

```css
:root {
  --page-bg: #f5f7fb;
  --surface-1: rgba(255, 255, 255, 0.88);
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest -v tests.test_ui_structure`
Expected: `PASS` for the structure assertions once the new classes and tokens exist.

- [ ] **Step 5: Commit**

```bash
git -C D:\Claude\gaokao-chem add tests/test_ui_structure.py static/style.css templates/base.html templates/index.html templates/login.html templates/register.html templates/vip.html templates/admin/index.html
git -C D:\Claude\gaokao-chem commit -m "test: lock UI refresh structure"
```

### Task 2: Refresh Shared Shell And User Pages

**Files:**
- Modify: `D:\Claude\gaokao-chem\templates\base.html`
- Modify: `D:\Claude\gaokao-chem\templates\index.html`
- Modify: `D:\Claude\gaokao-chem\templates\login.html`
- Modify: `D:\Claude\gaokao-chem\templates\register.html`
- Modify: `D:\Claude\gaokao-chem\templates\vip.html`
- Modify: `D:\Claude\gaokao-chem\static\style.css`
- Test: `tests/test_ui_structure.py`

- [ ] **Step 1: Write the failing test**

```python
def test_homepage_uses_new_search_shell(self):
    response = self.login().get("/")
    html = response.get_data(as_text=True)

    self.assertIn("search-shell", html)
    self.assertIn("filter-panel", html)
    self.assertIn("results-panel", html)
```

```python
def test_vip_page_uses_membership_layout(self):
    html = self.login().get("/api/vip/page").get_data(as_text=True)

    self.assertIn("membership-shell", html)
    self.assertIn("activation-panel", html)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest -v tests.test_ui_structure.UITemplateStructureTests.test_homepage_uses_new_search_shell tests.test_ui_structure.UITemplateStructureTests.test_vip_page_uses_membership_layout`
Expected: `FAIL` because the templates still render the old shell.

- [ ] **Step 3: Write minimal implementation**

```html
<main class="app-main">
  <section class="search-shell">
    <div class="search-hero"></div>
    <div class="query-layout">
      <aside class="query-sidebar filter-panel"></aside>
      <section class="query-main results-panel"></section>
    </div>
  </section>
</main>
```

```html
<section class="membership-shell">
  <div class="benefit-grid"></div>
  <div class="activation-panel"></div>
</section>
```

```css
.search-shell { max-width: 1320px; margin: 0 auto; padding: 32px 24px 56px; }
.search-hero { padding: 28px; border-radius: 28px; }
.filter-panel, .results-panel, .auth-card, .activation-panel { border-radius: 24px; }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest -v tests.test_ui_structure`
Expected: `PASS` for homepage, auth, and VIP structure tests.

- [ ] **Step 5: Commit**

```bash
git -C D:\Claude\gaokao-chem add templates/base.html templates/index.html templates/login.html templates/register.html templates/vip.html static/style.css
git -C D:\Claude\gaokao-chem commit -m "feat: refresh public site shell"
```

### Task 3: Refresh Admin Screens Into One Workspace System

**Files:**
- Modify: `D:\Claude\gaokao-chem\templates\admin\index.html`
- Modify: `D:\Claude\gaokao-chem\templates\admin\upload.html`
- Modify: `D:\Claude\gaokao-chem\templates\admin\review.html`
- Modify: `D:\Claude\gaokao-chem\templates\admin\papers.html`
- Modify: `D:\Claude\gaokao-chem\templates\admin\codes.html`
- Modify: `D:\Claude\gaokao-chem\static\style.css`
- Test: `tests/test_ui_structure.py`

- [ ] **Step 1: Write the failing test**

```python
def test_admin_dashboard_uses_workspace_layout(self):
    html = self.login("adminuser", "secret123").get("/admin").get_data(as_text=True)

    self.assertIn("admin-workspace", html)
    self.assertIn("workspace-header", html)
    self.assertIn("stats-grid", html)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest -v tests.test_ui_structure.UITemplateStructureTests.test_admin_dashboard_uses_workspace_layout`
Expected: `FAIL` because the admin templates still use the old dark shell.

- [ ] **Step 3: Write minimal implementation**

```html
<section class="admin-workspace">
  <aside class="admin-sidebar"></aside>
  <div class="admin-stage">
    <header class="workspace-header"></header>
    <section class="workspace-panel"></section>
  </div>
</section>
```

```css
.admin-workspace { display: grid; grid-template-columns: 260px minmax(0, 1fr); gap: 24px; }
.workspace-header, .workspace-panel, .edit-card, .stat-card { background: var(--surface-1); }
.admin-sidebar { background: rgba(255, 255, 255, 0.72); }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest -v tests.test_ui_structure`
Expected: `PASS` for admin dashboard structure and stylesheet token coverage.

- [ ] **Step 5: Commit**

```bash
git -C D:\Claude\gaokao-chem add templates/admin/index.html templates/admin/upload.html templates/admin/review.html templates/admin/papers.html templates/admin/codes.html static/style.css
git -C D:\Claude\gaokao-chem commit -m "feat: refresh admin workspace UI"
```

### Task 4: Verify The Refresh End To End

**Files:**
- Modify: `D:\Claude\gaokao-chem\static\app.js` only if UI hooks need to follow the new markup
- Test: `tests/test_ui_structure.py`

- [ ] **Step 1: Write the failing test**

```python
def test_stylesheet_contains_light_theme_tokens(self):
    with open("static/style.css", "r", encoding="utf-8") as f:
        css = f.read()

    self.assertIn("--page-bg", css)
    self.assertIn("--surface-1", css)
    self.assertIn(".search-hero", css)
    self.assertIn(".admin-workspace", css)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest -v tests.test_ui_structure.UITemplateStructureTests.test_stylesheet_contains_light_theme_tokens`
Expected: `FAIL` until the light-theme system is committed in `static/style.css`.

- [ ] **Step 3: Write minimal implementation**

```css
.search-bar,
.question-card,
.auth-card,
.workspace-panel,
.code-table-wrapper {
  background: var(--surface-1);
  border: 1px solid var(--line-soft);
  box-shadow: var(--shadow-card);
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest -v tests.test_ui_structure`
Expected: `PASS` with no failures.

- [ ] **Step 5: Commit**

```bash
git -C D:\Claude\gaokao-chem add static/style.css static/app.js tests/test_ui_structure.py
git -C D:\Claude\gaokao-chem commit -m "test: verify full UI refresh"
```
