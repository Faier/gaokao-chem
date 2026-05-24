# 高考化学题库商业化改版实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将现有 Flask 单体应用改造为可商用的高考化学题库系统，含登录验证、VIP激活码、后台管理和左右分栏查询界面。

**Architecture:** Flask 单体应用，4 个 Blueprint（auth/vip/query/admin）共享 models.py 数据层。SQLite + WAL 模式，jieba 分词 + FTS5 中文搜索，Flask-Login 做 session 认证，激活码 VIP 体系。

**Tech Stack:** Flask 3.1, SQLite + WAL, Flask-Login, jieba, pdfplumber, DeepSeek API

**Spec:** `docs/superpowers/specs/2026-05-24-gaokao-chem-commercial-redesign.md`

---

## File Map

| File | Action | Responsibility |
|------|--------|----------------|
| `config.py` | Modify | 新增 SECRET_KEY, VIP 配置 |
| `requirements.txt` | Modify | 新增 flask-login, jieba, werkzeug |
| `models.py` | Modify | 新增 users/codes 表、索引、jieba FTS |
| `auth.py` | Create | /auth Blueprint: 登录/注册/退出 |
| `vip.py` | Create | /api/vip Blueprint: 激活/状态查询 |
| `search.py` | Modify | 替换 FTS5 为 jieba 分词版本 |
| `query_bp.py` | Create | /api Blueprint: 题目查询 API |
| `admin_bp.py` | Create | /admin Blueprint: 上传/审核/激活码管理 |
| `parser.py` | Create | PDF 文本提取 + DeepSeek AI 解析 |
| `app.py` | Modify | 注册 Blueprint，初始化 Flask-Login |
| `create_admin.py` | Create | CLI 创建管理员账号 |
| `templates/base.html` | Create | 基础布局（导航栏 + 内容块） |
| `templates/login.html` | Create | 登录页 |
| `templates/register.html` | Create | 注册页 |
| `templates/index.html` | Modify | 左右分栏查询页 |
| `templates/admin/upload.html` | Create | 上传 PDF |
| `templates/admin/review.html` | Create | 审核解析结果 |
| `templates/admin/codes.html` | Create | 激活码管理 |
| `static/style.css` | Modify | 新增样式 |
| `static/app.js` | Create | 查询页交互逻辑 |
| `static/admin.js` | Create | 后台交互逻辑 |

**删除文件:** `crawler/`, `discover_papers.py`, `fetch_paper.py`, `batch_fetch.py`, `import_from_hf.py`, `pipeline.py`, `paper_urls*.json`, `check_content.py`, `import_pdf.py`

---

### Task 1: 环境准备

**Files:** `requirements.txt`, `config.py`

- [ ] **Step 1: 更新 requirements.txt**

写入 `D:\Claude\gaokao-chem\requirements.txt`：

```
flask==3.1.0
flask-login==0.6.3
requests==2.32.3
beautifulsoup4==4.12.3
lxml==5.3.0
pdfplumber==0.11.1
PyPDF2==3.0.1
jieba==0.42.1
```

- [ ] **Step 2: 安装依赖**

```bash
cd D:\Claude\gaokao-chem && pip install flask-login jieba
```

- [ ] **Step 3: 更新 config.py**

修改 `D:\Claude\gaokao-chem\config.py`，新增 SECRET_KEY 和 VIP 配置：

```python
import os
import secrets

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, 'data')
PAPERS_DIR = os.path.join(DATA_DIR, 'papers')
UPLOAD_DIR = os.path.join(DATA_DIR, 'uploads')
DB_PATH = os.path.join(DATA_DIR, 'chem.db')

SECRET_KEY = os.environ.get('SECRET_KEY', secrets.token_hex(32))

DEEPSEEK_API_KEY = os.environ.get(
    'DEEPSEEK_API_KEY',
    'sk-66681e1b197e4de2888b2fbc7f17ec48'
)
DEEPSEEK_API_URL = 'https://api.deepseek.com/v1/chat/completions'
DEEPSEEK_MODEL = 'deepseek-chat'

# VIP 配置
TRIAL_HOURS = 24          # 试用时长（小时）
VIP_CODE_LENGTH = 16      # 激活码长度
DEFAULT_PAGE_SIZE = 15    # 默认每页条数

os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(PAPERS_DIR, exist_ok=True)
os.makedirs(UPLOAD_DIR, exist_ok=True)
```

- [ ] **Step 4: Commit**

```bash
cd D:\Claude\gaokao-chem && git add requirements.txt config.py && git commit -m "chore: add flask-login, jieba, update config for commercial features"
```

---

### Task 2: 数据库模型改造

**Files:** `models.py`

- [ ] **Step 1: 重写 models.py**

用以下内容完全重写 `D:\Claude\gaokao-chem\models.py`：

```python
import sqlite3
import uuid
import jieba
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash

from config import DB_PATH

jieba.setLogLevel(20)


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS papers (
            id          TEXT PRIMARY KEY,
            year        INTEGER NOT NULL,
            province    TEXT NOT NULL,
            paper_type  TEXT NOT NULL,
            title       TEXT NOT NULL,
            file_path   TEXT,
            file_size   INTEGER,
            page_count  INTEGER,
            source_url  TEXT,
            status      TEXT DEFAULT 'pending',
            created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS questions (
            id            TEXT PRIMARY KEY,
            paper_id      TEXT NOT NULL REFERENCES papers(id),
            year          INTEGER NOT NULL,
            province      TEXT NOT NULL,
            paper_type    TEXT NOT NULL,
            question_num  INTEGER NOT NULL,
            q_type        TEXT NOT NULL,
            stem          TEXT NOT NULL,
            options       TEXT,
            answer        TEXT NOT NULL,
            explanation   TEXT,
            topics        TEXT,
            page_range    TEXT,
            source_url    TEXT,
            created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS users (
            id            TEXT PRIMARY KEY,
            username      TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            is_admin      INTEGER DEFAULT 0,
            trial_start   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            vip_expire_at TIMESTAMP,
            created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS activation_codes (
            id          TEXT PRIMARY KEY,
            code        TEXT UNIQUE NOT NULL,
            vip_days    INTEGER NOT NULL,
            created_by  TEXT,
            used_by     TEXT,
            used_at     TIMESTAMP,
            is_used     INTEGER DEFAULT 0,
            created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        -- Chinese FTS table using jieba tokenization
        CREATE VIRTUAL TABLE IF NOT EXISTS questions_fts USING fts5(
            stem,
            answer,
            explanation,
            topics,
            content='questions',
            content_rowid='rowid',
            tokenize='unicode61'
        );

        CREATE INDEX IF NOT EXISTS idx_q_year ON questions(year);
        CREATE INDEX IF NOT EXISTS idx_q_province ON questions(province);
        CREATE INDEX IF NOT EXISTS idx_q_type ON questions(q_type);
        CREATE INDEX IF NOT EXISTS idx_p_year ON papers(year);
        CREATE INDEX IF NOT EXISTS idx_p_province ON papers(province);
    """)
    conn.commit()
    conn.close()


# ── Paper helpers ──

def insert_paper(year, province, paper_type, title, file_path=None,
                 file_size=None, page_count=None, source_url=None):
    conn = get_db()
    paper_id = uuid.uuid4().hex
    conn.execute("""
        INSERT INTO papers (id, year, province, paper_type, title,
                            file_path, file_size, page_count, source_url)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (paper_id, year, province, paper_type, title,
          file_path, file_size, page_count, source_url))
    conn.commit()
    conn.close()
    return paper_id


def get_paper(paper_id):
    conn = get_db()
    row = conn.execute("SELECT * FROM papers WHERE id = ?", (paper_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def get_all_papers(year=None, province=None, status=None):
    conn = get_db()
    q = "SELECT * FROM papers WHERE 1=1"
    params = []
    if year:
        q += " AND year = ?"
        params.append(year)
    if province:
        q += " AND province = ?"
        params.append(province)
    if status:
        q += " AND status = ?"
        params.append(status)
    q += " ORDER BY year DESC, province"
    rows = conn.execute(q, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def paper_exists(year, province, paper_type):
    conn = get_db()
    row = conn.execute(
        "SELECT id FROM papers WHERE year=? AND province=? AND paper_type=?",
        (year, province, paper_type)
    ).fetchone()
    conn.close()
    return bool(row)


def update_paper_status(paper_id, status):
    conn = get_db()
    conn.execute("UPDATE papers SET status=? WHERE id=?", (status, paper_id))
    conn.commit()
    conn.close()


def delete_paper(paper_id):
    conn = get_db()
    conn.execute("DELETE FROM questions WHERE paper_id=?", (paper_id,))
    conn.execute("DELETE FROM papers WHERE id=?", (paper_id,))
    conn.commit()
    conn.close()


# ── Question helpers ──

def _tokenize(text):
    """Tokenize Chinese text with jieba, return space-separated tokens."""
    if not text:
        return ''
    return ' '.join(jieba.cut(text))


def insert_question(paper_id, year, province, paper_type, question_num,
                    q_type, stem, answer, options=None, explanation=None,
                    topics=None, page_range=None, source_url=None):
    conn = get_db()
    q_id = uuid.uuid4().hex
    conn.execute("""
        INSERT INTO questions (id, paper_id, year, province, paper_type,
                               question_num, q_type, stem, options, answer,
                               explanation, topics, page_range, source_url)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (q_id, paper_id, year, province, paper_type, question_num,
          q_type, stem, options, answer, explanation, topics,
          page_range, source_url))
    conn.commit()
    conn.close()
    return q_id


def get_question(q_id):
    conn = get_db()
    row = conn.execute("SELECT * FROM questions WHERE id = ?", (q_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def get_paper_questions(paper_id):
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM questions WHERE paper_id = ? ORDER BY question_num",
        (paper_id,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_stats():
    conn = get_db()
    total_q = conn.execute("SELECT COUNT(*) FROM questions").fetchone()[0]
    total_p = conn.execute("SELECT COUNT(*) FROM papers").fetchone()[0]
    years = conn.execute("SELECT MIN(year), MAX(year) FROM questions").fetchone()
    conn.close()
    return {
        'total_questions': total_q,
        'total_papers': total_p,
        'year_min': years[0],
        'year_max': years[1]
    }


def get_filter_options():
    conn = get_db()
    years = [r[0] for r in conn.execute(
        "SELECT DISTINCT year FROM questions ORDER BY year DESC"
    ).fetchall()]
    provinces = [r[0] for r in conn.execute(
        "SELECT DISTINCT province FROM questions ORDER BY province"
    ).fetchall()]
    q_types = [r[0] for r in conn.execute(
        "SELECT DISTINCT q_type FROM questions ORDER BY q_type"
    ).fetchall()]
    conn.close()
    return {'years': years, 'provinces': provinces, 'q_types': q_types}


def get_filter_counts():
    """Return filter options with question counts for each value."""
    conn = get_db()
    years = [dict(r) for r in conn.execute(
        "SELECT year as value, COUNT(*) as count FROM questions GROUP BY year ORDER BY year DESC"
    ).fetchall()]
    provinces = [dict(r) for r in conn.execute(
        "SELECT province as value, COUNT(*) as count FROM questions GROUP BY province ORDER BY province"
    ).fetchall()]
    q_types = [dict(r) for r in conn.execute(
        "SELECT q_type as value, COUNT(*) as count FROM questions GROUP BY q_type ORDER BY q_type"
    ).fetchall()]
    conn.close()
    return {'years': years, 'provinces': provinces, 'q_types': q_types}


# ── User helpers ──

def create_user(username, password, is_admin=0):
    conn = get_db()
    user_id = uuid.uuid4().hex
    conn.execute("""
        INSERT INTO users (id, username, password_hash, is_admin)
        VALUES (?, ?, ?, ?)
    """, (user_id, username, generate_password_hash(password), is_admin))
    conn.commit()
    conn.close()
    return user_id


def get_user_by_username(username):
    conn = get_db()
    row = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
    conn.close()
    return dict(row) if row else None


def get_user_by_id(user_id):
    conn = get_db()
    row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def verify_user(username, password):
    user = get_user_by_username(username)
    if not user:
        return None
    if check_password_hash(user['password_hash'], password):
        return user
    return None


def is_vip(user):
    """Check if user has valid VIP or is within trial period."""
    if user.get('is_admin'):
        return True
    if user.get('vip_expire_at'):
        from datetime import datetime as dt
        if dt.strptime(user['vip_expire_at'], '%Y-%m-%d %H:%M:%S') > dt.now():
            return True
    if user.get('trial_start'):
        from datetime import datetime as dt, timedelta
        from config import TRIAL_HOURS
        trial_start = dt.strptime(user['trial_start'], '%Y-%m-%d %H:%M:%S')
        if dt.now() - trial_start < timedelta(hours=TRIAL_HOURS):
            return True
    return False


def get_trial_remaining(user):
    """Return remaining trial hours, or 0 if expired."""
    from datetime import datetime as dt, timedelta
    from config import TRIAL_HOURS
    trial_start = dt.strptime(user['trial_start'], '%Y-%m-%d %H:%M:%S')
    elapsed = dt.now() - trial_start
    remaining = timedelta(hours=TRIAL_HOURS) - elapsed
    return max(0, round(remaining.total_seconds() / 3600, 1))


# ── Activation code helpers ──

def generate_codes(vip_days, count, created_by):
    import secrets
    conn = get_db()
    codes = []
    for _ in range(count):
        code_id = uuid.uuid4().hex
        code = 'GCHEM-' + secrets.token_hex(4).upper() + '-' + secrets.token_hex(4).upper()
        conn.execute("""
            INSERT INTO activation_codes (id, code, vip_days, created_by)
            VALUES (?, ?, ?, ?)
        """, (code_id, code, vip_days, created_by))
        codes.append(code)
    conn.commit()
    conn.close()
    return codes


def activate_code(code_str, username):
    from datetime import datetime as dt, timedelta
    conn = get_db()
    row = conn.execute(
        "SELECT * FROM activation_codes WHERE code = ? AND is_used = 0",
        (code_str.upper().strip(),)
    ).fetchone()
    if not row:
        conn.close()
        return False, '激活码无效或已被使用'

    code = dict(row)
    user = get_user_by_username(username)

    # Calculate new VIP expiry
    now = dt.now()
    if user.get('vip_expire_at'):
        current_expire = dt.strptime(user['vip_expire_at'], '%Y-%m-%d %H:%M:%S')
        new_expire = max(now, current_expire) + timedelta(days=code['vip_days'])
    else:
        new_expire = now + timedelta(days=code['vip_days'])

    conn.execute(
        "UPDATE users SET vip_expire_at=? WHERE username=?",
        (new_expire.strftime('%Y-%m-%d %H:%M:%S'), username)
    )
    conn.execute(
        "UPDATE activation_codes SET is_used=1, used_by=?, used_at=? WHERE id=?",
        (username, now.strftime('%Y-%m-%d %H:%M:%S'), code['id'])
    )
    conn.commit()
    conn.close()
    return True, f'激活成功，VIP 有效期至 {new_expire.strftime("%Y-%m-%d")}'


def get_all_codes(used=None):
    conn = get_db()
    q = "SELECT * FROM activation_codes WHERE 1=1"
    params = []
    if used is not None:
        q += " AND is_used = ?"
        params.append(1 if used else 0)
    q += " ORDER BY created_at DESC"
    rows = conn.execute(q, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]
```

- [ ] **Step 2: 初始化数据库验证**

```bash
cd D:\Claude\gaokao-chem && python -c "from models import init_db; init_db(); print('DB init OK')"
```

- [ ] **Step 3: Commit**

```bash
cd D:\Claude\gaokao-chem && git add models.py && git commit -m "feat: add users/codes tables, jieba FTS, VIP helpers to models"
```

---

### Task 3: 认证模块

**Files:** `auth.py`, `templates/login.html`, `templates/register.html`

- [ ] **Step 1: 创建 auth.py**

写入 `D:\Claude\gaokao-chem\auth.py`：

```python
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_user, logout_user, login_required, current_user

from models import get_user_by_id, create_user, verify_user, get_user_by_username, is_vip, get_trial_remaining

auth_bp = Blueprint('auth', __name__, url_prefix='/auth')


class User:
    """Flask-Login user wrapper with direct VIP properties."""
    def __init__(self, user_dict):
        self.id = user_dict['id']
        self.username = user_dict['username']
        self.is_admin = bool(user_dict.get('is_admin'))
        self.vip_expire_at = user_dict.get('vip_expire_at')
        self.trial_start = user_dict.get('trial_start')
        self._data = user_dict

    @property
    def is_active(self):
        return True

    @property
    def is_authenticated(self):
        return True

    @property
    def is_anonymous(self):
        return False

    def get_id(self):
        return self.id

    def has_vip(self):
        return is_vip(self._data)

    def trial_remaining_hours(self):
        return get_trial_remaining(self._data)


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        user = verify_user(username, password)
        if user:
            login_user(User(user), remember=True)
            next_page = request.args.get('next')
            return redirect(next_page or url_for('index'))
        flash('用户名或密码错误', 'error')
    return render_template('login.html')


@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        confirm = request.form.get('confirm', '')

        if len(username) < 2 or len(username) > 32:
            flash('用户名长度 2-32 个字符', 'error')
        elif len(password) < 6:
            flash('密码至少 6 位', 'error')
        elif password != confirm:
            flash('两次密码不一致', 'error')
        elif get_user_by_username(username):
            flash('用户名已存在', 'error')
        else:
            create_user(username, password)
            user = get_user_by_username(username)
            login_user(User(user), remember=True)
            return redirect(url_for('index'))
    return render_template('register.html')


@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('auth.login'))
```

- [ ] **Step 2: 创建 login.html**

写入 `D:\Claude\gaokao-chem\templates\login.html`：

```html
{% extends "base.html" %}
{% block title %}登录{% endblock %}
{% block body_class %}auth-page{% endblock %}
{% block content %}
<div class="auth-container">
  <h2>登录</h2>
  {% with msg = get_flashed_messages(category_filter=['error']) %}
  {% if msg %}<div class="flash-error">{{ msg[0] }}</div>{% endif %}
  {% endwith %}
  <form method="post">
    <label>用户名</label>
    <input type="text" name="username" required autocomplete="username">
    <label>密码</label>
    <input type="password" name="password" required autocomplete="current-password">
    <button type="submit">登录</button>
  </form>
  <p class="auth-switch">没有账号？<a href="{{ url_for('auth.register') }}">去注册</a></p>
</div>
{% endblock %}
```

- [ ] **Step 3: 创建 register.html**

写入 `D:\Claude\gaokao-chem\templates\register.html`：

```html
{% extends "base.html" %}
{% block title %}注册{% endblock %}
{% block body_class %}auth-page{% endblock %}
{% block content %}
<div class="auth-container">
  <h2>注册</h2>
  {% with msg = get_flashed_messages(category_filter=['error']) %}
  {% if msg %}<div class="flash-error">{{ msg[0] }}</div>{% endif %}
  {% endwith %}
  <form method="post">
    <label>用户名</label>
    <input type="text" name="username" required autocomplete="username">
    <label>密码（至少 6 位）</label>
    <input type="password" name="password" required autocomplete="new-password">
    <label>确认密码</label>
    <input type="password" name="confirm" required autocomplete="new-password">
    <button type="submit">注册</button>
  </form>
  <p class="auth-switch">已有账号？<a href="{{ url_for('auth.login') }}">去登录</a></p>
</div>
{% endblock %}
```

- [ ] **Step 4: 创建 base.html**

写入 `D:\Claude\gaokao-chem\templates\base.html`：

```html
<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{% block title %}高考化学题库{% endblock %}</title>
<link rel="stylesheet" href="/static/style.css">
{% block head %}{% endblock %}
</head>
<body class="{% block body_class %}{% endblock %}">
<nav class="top-nav">
  <div class="nav-left">
    <a href="/" class="nav-logo">高考化学题库</a>
  </div>
  <div class="nav-right">
    {% if current_user.is_authenticated %}
      <span class="nav-user">{{ current_user.username }}</span>
      {% if current_user.is_admin %}
        <span class="nav-badge admin">管理员</span>
        <a href="/admin" class="nav-link">后台</a>
      {% elif current_user.has_vip() %}
        <span class="nav-badge vip">VIP {{ current_user.vip_expire_at[:10] if current_user.vip_expire_at else '' }}</span>
      {% else %}
        <span class="nav-badge trial">试用 {{ current_user.trial_remaining_hours() }}h</span>
        <a href="/api/vip/page" class="nav-link">充值</a>
      {% endif %}
      <a href="/auth/logout" class="nav-link">退出</a>
    {% else %}
      <a href="/auth/login" class="nav-link">登录</a>
      <a href="/auth/register" class="nav-link">注册</a>
    {% endif %}
  </div>
</nav>
<main>
{% block content %}{% endblock %}
</main>
{% block scripts %}{% endblock %}
</body>
</html>
```

- [ ] **Step 5: Commit**

```bash
cd D:\Claude\gaokao-chem && git add auth.py templates/login.html templates/register.html templates/base.html && git commit -m "feat: add auth blueprint with login/register and base template"
```

---

### Task 4: VIP 模块

**Files:** `vip.py`

- [ ] **Step 1: 创建 vip.py**

写入 `D:\Claude\gaokao-chem\vip.py`：

```python
from flask import Blueprint, jsonify, request, render_template
from flask_login import login_required, current_user

from models import activate_code

vip_bp = Blueprint('vip', __name__, url_prefix='/api/vip')


@vip_bp.route('/status')
@login_required
def vip_status():
    return jsonify({
        'username': current_user.username,
        'is_admin': current_user.is_admin,
        'vip': current_user.has_vip(),
        'vip_expire_at': current_user.vip_expire_at,
        'trial_remaining_hours': current_user.trial_remaining_hours(),
    })


@vip_bp.route('/activate', methods=['POST'])
@login_required
def activate():
    code = request.form.get('code', '').strip()
    if not code:
        return jsonify({'ok': False, 'msg': '请输入激活码'}), 400
    ok, msg = activate_code(code, current_user.username)
    return jsonify({'ok': ok, 'msg': msg})


@vip_bp.route('/page')
@login_required
def vip_page():
    return render_template('vip.html')
```

- [ ] **Step 2: 创建 vip.html 充值页面**

写入 `D:\Claude\gaokao-chem\templates\vip.html`：

```html
{% extends "base.html" %}
{% block title %}VIP 充值{% endblock %}
{% block body_class %}auth-page{% endblock %}
{% block content %}
<div class="auth-container">
  <h2>VIP 充值</h2>
  <p>输入激活码开通 VIP</p>
  <form id="vip-form">
    <label>激活码</label>
    <input type="text" id="code-input" placeholder="GCHEM-XXXX-XXXX" required>
    <button type="submit">激活</button>
  </form>
  <div id="vip-result" style="margin-top:12px;"></div>
</div>
<script>
document.getElementById('vip-form').addEventListener('submit', function(e) {
  e.preventDefault();
  var code = document.getElementById('code-input').value;
  var formData = new FormData();
  formData.append('code', code);
  fetch('/api/vip/activate', { method: 'POST', body: formData })
    .then(function(r) { return r.json(); })
    .then(function(d) {
      var el = document.getElementById('vip-result');
      el.textContent = d.msg;
      el.style.color = d.ok ? '#4caf50' : '#f44336';
      if (d.ok) { setTimeout(function() { location.reload(); }, 1500); }
    });
});
</script>
{% endblock %}
```

- [ ] **Step 3: Commit**

```bash
cd D:\Claude\gaokao-chem && git add vip.py templates/vip.html && git commit -m "feat: add VIP activation code system"
```

---

### Task 5: PDF 解析模块

**Files:** `parser.py`

- [ ] **Step 1: 创建 parser.py**

写入 `D:\Claude\gaokao-chem\parser.py`，从 `crawler/parse.py` 提取核心逻辑：

```python
"""PDF text extraction and DeepSeek AI parsing for exam papers."""

import json
import re
import os
import requests

from config import DEEPSEEK_API_KEY, DEEPSEEK_API_URL, DEEPSEEK_MODEL

try:
    import pdfplumber
    HAS_PDFPLUMBER = True
except ImportError:
    HAS_PDFPLUMBER = False

try:
    import PyPDF2
    HAS_PYPDF2 = True
except ImportError:
    HAS_PYPDF2 = False


EXTRACTION_PROMPT = """你是一个高考化学试卷解析专家。请将以下试卷内容解析为结构化的题目列表。

一份标准的高考化学试卷通常包含 10-15 道题目（7道选择题+3道必做大题+2道选做题）。
请只提取真正的考试题目，不要提取：试卷说明、答题须知、评分标准、目录、页眉页脚等非题目内容。

对于每道题目，提取以下字段并以 JSON 数组格式返回：
- question_num: 题号（整数）
- q_type: 题型，只能是 "选择题" / "填空题" / "实验题" / "计算题" / "简答题" 之一
- stem: 题干原文（完整保留，包括化学方程式和符号）
- options: 选项列表，如 [{"A":"..."},{"B":"..."}]，选择题必有，其他题型为空数组
- answer: 标准答案
- explanation: 题目解析（如果有的话）
- topics: 涉及的知识点关键词，用空格分隔，如 "氧化还原反应 电化学 原电池"

重要：每道大题（如工艺流程题、实验题）应作为一个整体题目，不要将其拆分成多个小题。
一道大题下面的多个小问应该合并到 stem 字段中。

请严格按以下 JSON 格式返回，不要包含其他内容：
```json
{
  "questions": [
    {
      "question_num": 1,
      "q_type": "选择题",
      "stem": "...",
      "options": [{"A":"..."},{"B":"..."}],
      "answer": "B",
      "explanation": "...",
      "topics": "关键词1 关键词2"
    }
  ]
}
```"""


def extract_text_from_pdf(filepath):
    """Extract text from a PDF file. Tries pdfplumber first, then PyPDF2."""
    text_parts = []

    if HAS_PDFPLUMBER:
        try:
            with pdfplumber.open(filepath) as pdf:
                for page in pdf.pages:
                    t = page.extract_text()
                    if t:
                        text_parts.append(t)
            result = '\n\n'.join(text_parts)
            if result.strip():
                return result
        except Exception as e:
            pass

    if HAS_PYPDF2:
        try:
            with open(filepath, 'rb') as f:
                reader = PyPDF2.PdfReader(f)
                for page in reader.pages:
                    t = page.extract_text()
                    if t:
                        text_parts.append(t)
            result = '\n\n'.join(text_parts)
            if result.strip():
                return result
        except Exception as e:
            pass

    return None


def call_deepseek(paper_text, retry=True):
    """Send extraction request to DeepSeek API, return parsed JSON or None."""
    payload = {
        "model": DEEPSEEK_MODEL,
        "messages": [
            {"role": "system", "content": EXTRACTION_PROMPT},
            {"role": "user", "content": paper_text[:30000]}
        ],
        "max_tokens": 8000,
        "temperature": 0.1
    }
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
    }
    try:
        resp = requests.post(DEEPSEEK_API_URL, headers=headers, json=payload, timeout=180)
        if resp.status_code != 200:
            return {'error': f'API HTTP {resp.status_code}', 'raw': resp.text[:300]}
        result = resp.json()
        content = result["choices"][0]["message"]["content"]

        m = re.search(r'```(?:json)?\s*([\s\S]*?)```', content)
        if m:
            content = m.group(1)
        else:
            m = re.search(r'\{[\s\S]*\}', content)
            if m:
                content = m.group()

        return json.loads(content)

    except json.JSONDecodeError as e:
        if retry:
            return call_deepseek(paper_text[:20000], retry=False)
        return {'error': f'JSON parse failed: {e}', 'raw': content[:500] if 'content' in dir() else ''}
    except (KeyError, requests.RequestException) as e:
        return {'error': f'API call failed: {e}'}


def parse_pdf_to_questions(filepath):
    """Parse a PDF file into structured question data. Returns list of question dicts."""
    text = extract_text_from_pdf(filepath)
    if not text:
        return {'error': 'PDF 文字提取失败，文件可能为扫描件或加密'}
    if len(text) < 50:
        return {'error': 'PDF 文字内容过少'}

    result = call_deepseek(text)
    if not result:
        return {'error': 'AI 解析失败，请重试'}
    if 'error' in result:
        return result

    return {'questions': result.get('questions', []), 'raw_text': text[:5000]}
```

- [ ] **Step 2: Commit**

```bash
cd D:\Claude\gaokao-chem && git add parser.py && git commit -m "feat: extract PDF parsing logic to parser.py"
```

---

### Task 6: 查询 API Blueprint

**Files:** `query_bp.py`, `search.py`

- [ ] **Step 1: 更新 search.py — 纯 jieba 分词搜索**

用以下内容重写 `D:\Claude\gaokao-chem\search.py`：

```python
"""Keyword search via jieba-tokenized FTS5 for Chinese text."""

import jieba
from models import get_db

jieba.setLogLevel(20)


def _tokenize_query(q):
    """Tokenize Chinese query with jieba, return FTS5 MATCH compatible string."""
    tokens = [t.strip() for t in jieba.cut(q) if t.strip()]
    return ' AND '.join(tokens)


def search_questions(keyword='', page=1, size=15, year=None, province=None, q_type=None):
    """Paginated question search with optional filters.

    Uses a like-based strategy for reliability: FTS5 with porter
    doesn't play well with jieba tokens. Instead we use simple
    LIKE matching on jieba-tokenized segments.
    """
    conn = get_db()

    where_parts = []
    params = []

    if keyword and keyword.strip():
        tokens = [t.strip() for t in jieba.cut(keyword) if len(t.strip()) >= 1]
        if tokens:
            like_parts = []
            for token in tokens:
                like_parts.append("(q.stem LIKE ? OR q.answer LIKE ? OR q.explanation LIKE ? OR q.topics LIKE ?)")
                pattern = '%' + token.replace('%', '\\%') + '%'
                params.extend([pattern, pattern, pattern, pattern])
            where_parts.append("(" + " AND ".join(like_parts) + ")")

    if year:
        where_parts.append("q.year = ?")
        params.append(int(year))
    if province:
        where_parts.append("q.province = ?")
        params.append(province)
    if q_type:
        where_parts.append("q.q_type = ?")
        params.append(q_type)

    where_sql = (" AND ".join(where_parts)) if where_parts else "1=1"

    total = conn.execute(
        f"SELECT COUNT(*) FROM questions q WHERE {where_sql}", params
    ).fetchone()[0]

    offset = (page - 1) * size
    rows = conn.execute(
        f"SELECT * FROM questions q WHERE {where_sql} ORDER BY q.year DESC LIMIT ? OFFSET ?",
        params + [size, offset]
    ).fetchall()
    conn.close()

    questions = []
    for row in rows:
        qd = dict(row)
        try:
            qd['options'] = json.loads(qd['options']) if qd.get('options') else []
        except Exception:
            qd['options'] = []
        questions.append(qd)

    return {
        'total': total,
        'page': page,
        'size': size,
        'questions': questions
    }


import json
```

- [ ] **Step 2: 创建 query_bp.py**

写入 `D:\Claude\gaokao-chem\query_bp.py`：

```python
import json
from flask import Blueprint, jsonify, request
from flask_login import login_required, current_user

from models import get_question, get_paper, get_filter_counts
from search import search_questions

query_bp = Blueprint('query', __name__, url_prefix='/api')


def vip_required(f):
    from functools import wraps
    @wraps(f)
    @login_required
    def wrapper(*args, **kwargs):
        if not current_user.has_vip():
            return jsonify({'error': '请先开通VIP', 'code': 'VIP_REQUIRED'}), 403
        return f(*args, **kwargs)
    return wrapper


@query_bp.route('/questions')
@vip_required
def api_questions():
    keyword = request.args.get('keyword', '').strip()
    page = request.args.get('page', 1, type=int)
    size = request.args.get('size', 15, type=int)
    year = request.args.get('year', type=int)
    province = request.args.get('province', '').strip() or None
    q_type = request.args.get('q_type', '').strip() or None

    result = search_questions(
        keyword=keyword, page=page, size=size,
        year=year, province=province, q_type=q_type
    )
    return jsonify(result)


@query_bp.route('/question/<q_id>')
@vip_required
def api_question(q_id):
    question = get_question(q_id)
    if not question:
        return jsonify({'error': 'not found'}), 404
    try:
        question['options'] = json.loads(question['options']) if question.get('options') else []
    except Exception:
        question['options'] = []
    paper = get_paper(question['paper_id'])
    question['paper'] = paper
    return jsonify(question)


@query_bp.route('/filters')
@vip_required
def api_filters():
    return jsonify(get_filter_counts())
```

- [ ] **Step 3: Commit**

```bash
cd D:\Claude\gaokao-chem && git add search.py query_bp.py && git commit -m "feat: add jieba-based search and query API blueprint"
```

---

### Task 7: 管理后台 Blueprint

**Files:** `admin_bp.py`, `templates/admin/upload.html`, `templates/admin/review.html`, `templates/admin/codes.html`

- [ ] **Step 1: 创建 admin_bp.py**

写入 `D:\Claude\gaokao-chem\admin_bp.py`：

```python
import json
import os
from flask import Blueprint, render_template, request, jsonify, redirect, url_for
from flask_login import login_required, current_user
from functools import wraps

from models import (
    insert_paper, insert_question, get_paper, get_paper_questions,
    get_all_papers, update_paper_status, delete_paper,
    generate_codes, get_all_codes, get_stats
)
from parser import parse_pdf_to_questions
from config import UPLOAD_DIR

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')


def admin_required(f):
    @wraps(f)
    @login_required
    def wrapper(*args, **kwargs):
        if not current_user.is_admin:
            return jsonify({'error': '需要管理员权限'}), 403
        return f(*args, **kwargs)
    return wrapper


@admin_bp.route('/')
@admin_required
def index():
    stats = get_stats()
    pending = get_all_papers(status='pending')
    return render_template('admin/index.html', stats=stats, pending=pending)


@admin_bp.route('/upload', methods=['GET', 'POST'])
@admin_required
def upload():
    if request.method == 'POST':
        year = request.form.get('year', type=int)
        province = request.form.get('province', '').strip()
        paper_type = request.form.get('paper_type', '').strip()
        title = request.form.get('title', '').strip()
        file = request.files.get('pdf')

        if not all([year, province, paper_type, title, file]):
            return jsonify({'ok': False, 'msg': '请填写所有字段并选择 PDF 文件'}), 400

        filename = f"{year}_{province}_{paper_type}.pdf"
        filepath = os.path.join(UPLOAD_DIR, filename)
        file.save(filepath)

        paper_id = insert_paper(
            year=year, province=province, paper_type=paper_type,
            title=title, file_path=filepath,
            file_size=os.path.getsize(filepath)
        )
        return jsonify({'ok': True, 'paper_id': paper_id, 'msg': '上传成功'})

    return render_template('admin/upload.html')


@admin_bp.route('/parse/<paper_id>')
@admin_required
def parse_review(paper_id):
    paper = get_paper(paper_id)
    if not paper:
        return jsonify({'error': 'not found'}), 404

    result = parse_pdf_to_questions(paper['file_path'])
    if 'error' in result:
        return render_template('admin/review.html', paper=paper, error=result['error'], questions=[])

    return render_template('admin/review.html', paper=paper, questions=result['questions'])


@admin_bp.route('/parse/<paper_id>/confirm', methods=['POST'])
@admin_required
def parse_confirm(paper_id):
    paper = get_paper(paper_id)
    if not paper:
        return jsonify({'error': 'not found'}), 404

    data = request.get_json()
    questions = data.get('questions', [])

    for q in questions:
        options_json = json.dumps(q.get('options', []), ensure_ascii=False)
        insert_question(
            paper_id=paper_id,
            year=paper['year'],
            province=paper['province'],
            paper_type=paper['paper_type'],
            question_num=q.get('question_num', 1),
            q_type=q.get('q_type', '选择题'),
            stem=q.get('stem', ''),
            answer=q.get('answer', ''),
            options=options_json,
            explanation=q.get('explanation', ''),
            topics=q.get('topics', ''),
        )

    update_paper_status(paper_id, 'confirmed')
    return jsonify({'ok': True, 'msg': f'已入库 {len(questions)} 道题目'})


@admin_bp.route('/parse/<paper_id>/delete', methods=['POST'])
@admin_required
def parse_delete(paper_id):
    delete_paper(paper_id)
    return jsonify({'ok': True, 'msg': '已删除'})


@admin_bp.route('/papers')
@admin_required
def papers_list():
    papers = get_all_papers()
    return render_template('admin/papers.html', papers=papers)


@admin_bp.route('/codes')
@admin_required
def codes():
    all_codes = get_all_codes()
    return render_template('admin/codes.html', codes=all_codes)


@admin_bp.route('/codes/generate', methods=['POST'])
@admin_required
def codes_generate():
    vip_days = request.form.get('vip_days', 30, type=int)
    count = request.form.get('count', 10, type=int)
    codes = generate_codes(vip_days, count, current_user.username)
    return jsonify({'ok': True, 'codes': codes})
```

- [ ] **Step 2: 创建 admin/upload.html**

写入 `D:\Claude\gaokao-chem\templates\admin\upload.html`：

```html
{% extends "base.html" %}
{% block title %}上传试卷{% endblock %}
{% block content %}
<div class="admin-layout">
  <aside class="admin-sidebar">
    <h3>管理后台</h3>
    <a href="/admin">概览</a>
    <a href="/admin/upload" class="active">上传试卷</a>
    <a href="/admin/papers">试卷列表</a>
    <a href="/admin/codes">激活码</a>
  </aside>
  <div class="admin-content">
    <h2>上传试卷 PDF</h2>
    <form id="upload-form" enctype="multipart/form-data">
      <label>年份</label>
      <input type="number" name="year" required placeholder="如 2024">
      <label>省份</label>
      <input type="text" name="province" required placeholder="如 全国卷">
      <label>试卷类型</label>
      <input type="text" name="paper_type" required placeholder="如 理综">
      <label>试卷标题</label>
      <input type="text" name="title" required placeholder="如 2024年高考全国卷理综化学">
      <label>PDF 文件</label>
      <input type="file" name="pdf" accept=".pdf" required>
      <button type="submit">上传并解析</button>
    </form>
    <div id="upload-result"></div>
  </div>
</div>
<script>
document.getElementById('upload-form').addEventListener('submit', function(e) {
  e.preventDefault();
  var fd = new FormData(this);
  var btn = this.querySelector('button');
  btn.textContent = '上传中...';
  btn.disabled = true;
  fetch('/admin/upload', { method: 'POST', body: fd })
    .then(function(r) { return r.json(); })
    .then(function(d) {
      var el = document.getElementById('upload-result');
      if (d.ok) {
        el.innerHTML = '<div class="flash-ok">' + d.msg + ' <a href="/admin/parse/' + d.paper_id + '">去审核</a></div>';
      } else {
        el.innerHTML = '<div class="flash-error">' + d.msg + '</div>';
      }
      btn.textContent = '上传并解析';
      btn.disabled = false;
    });
});
</script>
{% endblock %}
```

- [ ] **Step 3: 创建 admin/review.html**

写入 `D:\Claude\gaokao-chem\templates\admin\review.html`：

```html
{% extends "base.html" %}
{% block title %}审核解析 — {{ paper.title }}{% endblock %}
{% block content %}
<div class="admin-layout">
  <aside class="admin-sidebar">
    <h3>管理后台</h3>
    <a href="/admin">概览</a>
    <a href="/admin/upload">上传试卷</a>
    <a href="/admin/papers">试卷列表</a>
    <a href="/admin/codes">激活码</a>
  </aside>
  <div class="admin-content">
    <h2>{{ paper.title }} <small>{{ paper.year }} {{ paper.province }} {{ paper.paper_type }}</small></h2>
    {% if error %}
      <div class="flash-error">{{ error }}</div>
      <a href="/admin/upload">重新上传</a>
    {% else %}
      <p>AI 解析出 {{ questions|length }} 道题目，请审核后确认入库</p>
      <div id="questions-editor">
        {% for q in questions %}
        <div class="edit-card" data-index="{{ loop.index0 }}">
          <h3>第 {{ q.question_num }} 题 — {{ q.q_type }}</h3>
          <label>题型</label>
          <input type="text" name="q_type" value="{{ q.q_type }}">
          <label>题干</label>
          <textarea name="stem" rows="4">{{ q.stem }}</textarea>
          <label>选项 (JSON)</label>
          <textarea name="options" rows="2">{{ q.options | tojson }}</textarea>
          <label>答案</label>
          <input type="text" name="answer" value="{{ q.answer }}">
          <label>解析</label>
          <textarea name="explanation" rows="3">{{ q.explanation or '' }}</textarea>
          <label>知识点（空格分隔）</label>
          <input type="text" name="topics" value="{{ q.topics or '' }}">
          <input type="hidden" name="question_num" value="{{ q.question_num }}">
        </div>
        {% endfor %}
      </div>
      <button id="confirm-btn" onclick="confirmQuestions('{{ paper.id }}')">确认入库</button>
      <button id="delete-btn" class="danger" onclick="deletePaper('{{ paper.id }}')">删除此试卷</button>
      <div id="confirm-result"></div>
    {% endif %}
  </div>
</div>
<script>
function confirmQuestions(paperId) {
  var questions = [];
  document.querySelectorAll('.edit-card').forEach(function(card) {
    var q = {};
    card.querySelectorAll('input, textarea').forEach(function(el) {
      var name = el.name;
      if (name === 'options') {
        try { q[name] = JSON.parse(el.value); } catch(e) { q[name] = []; }
      } else if (name === 'question_num') {
        q[name] = parseInt(el.value);
      } else {
        q[name] = el.value;
      }
    });
    questions.push(q);
  });
  var btn = document.getElementById('confirm-btn');
  btn.disabled = true;
  btn.textContent = '入库中...';
  fetch('/admin/parse/' + paperId + '/confirm', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ questions: questions })
  })
  .then(function(r) { return r.json(); })
  .then(function(d) {
    var el = document.getElementById('confirm-result');
    el.textContent = d.msg;
    el.style.color = d.ok ? '#4caf50' : '#f44336';
    if (d.ok) { setTimeout(function() { location.href = '/admin/papers'; }, 2000); }
  });
}
function deletePaper(paperId) {
  if (!confirm('确定删除？')) return;
  fetch('/admin/parse/' + paperId + '/delete', { method: 'POST' })
    .then(function(r) { return r.json(); })
    .then(function(d) {
      if (d.ok) { location.href = '/admin/papers'; }
    });
}
</script>
{% endblock %}
```

- [ ] **Step 4: 创建 admin/codes.html** 和 **admin/index.html** 和 **admin/papers.html**

写入 `D:\Claude\gaokao-chem\templates\admin\codes.html`：

```html
{% extends "base.html" %}
{% block title %}激活码管理{% endblock %}
{% block content %}
<div class="admin-layout">
  <aside class="admin-sidebar">
    <h3>管理后台</h3>
    <a href="/admin">概览</a>
    <a href="/admin/upload">上传试卷</a>
    <a href="/admin/papers">试卷列表</a>
    <a href="/admin/codes" class="active">激活码</a>
  </aside>
  <div class="admin-content">
    <h2>激活码管理</h2>
    <form id="gen-form">
      <label>VIP 天数</label>
      <input type="number" name="vip_days" value="30" min="1" max="3650">
      <label>生成数量</label>
      <input type="number" name="count" value="10" min="1" max="100">
      <button type="submit">生成激活码</button>
    </form>
    <div id="gen-result"></div>
    <h3>所有激活码</h3>
    <table class="code-table">
      <thead><tr><th>激活码</th><th>天数</th><th>状态</th><th>使用者</th><th>使用时间</th></tr></thead>
      <tbody>
      {% for c in codes %}
      <tr>
        <td><code>{{ c.code }}</code></td>
        <td>{{ c.vip_days }}</td>
        <td>{% if c.is_used %}<span class="badge-used">已用</span>{% else %}<span class="badge-ok">可用</span>{% endif %}</td>
        <td>{{ c.used_by or '-' }}</td>
        <td>{{ c.used_at or '-' }}</td>
      </tr>
      {% endfor %}
      </tbody>
    </table>
  </div>
</div>
<script>
document.getElementById('gen-form').addEventListener('submit', function(e) {
  e.preventDefault();
  var fd = new FormData(this);
  fetch('/admin/codes/generate', { method: 'POST', body: fd })
    .then(function(r) { return r.json(); })
    .then(function(d) {
      var el = document.getElementById('gen-result');
      if (d.ok) {
        el.innerHTML = '<div class="flash-ok">生成成功:<br><textarea rows="5" style="width:100%">' + d.codes.join('\\n') + '</textarea></div>';
      }
    });
});
</script>
{% endblock %}
```

写入 `D:\Claude\gaokao-chem\templates\admin\index.html`：

```html
{% extends "base.html" %}
{% block title %}管理后台{% endblock %}
{% block content %}
<div class="admin-layout">
  <aside class="admin-sidebar">
    <h3>管理后台</h3>
    <a href="/admin" class="active">概览</a>
    <a href="/admin/upload">上传试卷</a>
    <a href="/admin/papers">试卷列表</a>
    <a href="/admin/codes">激活码</a>
  </aside>
  <div class="admin-content">
    <h2>概览</h2>
    <div class="stats-grid">
      <div class="stat-card"><h3>{{ stats.total_questions }}</h3><p>题目总数</p></div>
      <div class="stat-card"><h3>{{ stats.total_papers }}</h3><p>试卷总数</p></div>
      <div class="stat-card"><h3>{{ pending|length }}</h3><p>待审核</p></div>
    </div>
  </div>
</div>
{% endblock %}
```

写入 `D:\Claude\gaokao-chem\templates\admin\papers.html`：

```html
{% extends "base.html" %}
{% block title %}试卷列表{% endblock %}
{% block content %}
<div class="admin-layout">
  <aside class="admin-sidebar">
    <h3>管理后台</h3>
    <a href="/admin">概览</a>
    <a href="/admin/upload">上传试卷</a>
    <a href="/admin/papers" class="active">试卷列表</a>
    <a href="/admin/codes">激活码</a>
  </aside>
  <div class="admin-content">
    <h2>试卷列表</h2>
    <table class="code-table">
      <thead><tr><th>标题</th><th>年份</th><th>省份</th><th>类型</th><th>状态</th><th>操作</th></tr></thead>
      <tbody>
      {% for p in papers %}
      <tr>
        <td>{{ p.title }}</td>
        <td>{{ p.year }}</td>
        <td>{{ p.province }}</td>
        <td>{{ p.paper_type }}</td>
        <td>{% if p.status == 'confirmed' %}<span class="badge-ok">已入库</span>{% else %}<span class="badge-used">待审核</span>{% endif %}</td>
        <td>
          {% if p.status != 'confirmed' %}<a href="/admin/parse/{{ p.id }}">审核</a>{% else %}已入库{% endif %}
        </td>
      </tr>
      {% endfor %}
      </tbody>
    </table>
  </div>
</div>
{% endblock %}
```

- [ ] **Step 5: Commit**

```bash
cd D:\Claude\gaokao-chem && git add admin_bp.py templates/admin/ && git commit -m "feat: add admin backend with upload, review, and code management"
```

---

### Task 8: 查询页面重设计

**Files:** `templates/index.html`, `static/style.css`, `static/app.js`

- [ ] **Step 1: 重写 index.html 为左右分栏布局**

用以下内容重写 `D:\Claude\gaokao-chem\templates\index.html`：

```html
{% extends "base.html" %}
{% block title %}高考化学题库{% endblock %}
{% block content %}
<div class="query-layout">
  <!-- 左侧筛选区 -->
  <aside class="query-sidebar">
    <h3>筛选条件</h3>
    <div class="filter-section">
      <h4>年份</h4>
      <div class="filter-tags" id="filter-years"></div>
    </div>
    <div class="filter-section">
      <h4>省份</h4>
      <div class="filter-tags" id="filter-provinces"></div>
    </div>
    <div class="filter-section">
      <h4>题型</h4>
      <div class="filter-tags" id="filter-types"></div>
    </div>
    <div class="filter-summary" id="filter-summary" style="display:none">
      <div>已选:</div>
      <div id="selected-tags"></div>
      <div>结果: <span id="selected-count">0</span> 条</div>
    </div>
  </aside>

  <!-- 右侧内容区 -->
  <div class="query-main">
    <div class="search-bar">
      <input type="text" id="search-input" placeholder="搜索题干 / 答案 / 解析 / 知识点..." autocomplete="off">
      <button id="search-btn">搜索</button>
    </div>
    <div id="results-container">
      <div class="empty-state"><p>点击左侧筛选条件或输入关键词开始查询</p></div>
    </div>
    <div id="pagination"></div>
  </div>
</div>

<div id="detail-modal" class="modal" style="display:none">
  <div class="modal-content">
    <span class="modal-close" onclick="closeModal()">&times;</span>
    <div id="modal-body"></div>
  </div>
</div>
{% endblock %}
{% block scripts %}
<script src="/static/app.js"></script>
{% endblock %}
```

- [ ] **Step 2: 创建 static/app.js**

写入 `D:\Claude\gaokao-chem\static\app.js`：

```javascript
// State
var state = { year: null, province: null, q_type: null, keyword: '', page: 1, size: 15 };
var filters = null;

// Init
fetch('/api/filters')
  .then(function(r) { return r.json(); })
  .then(function(d) {
    filters = d;
    renderFilterTags('filter-years', d.years, 'year');
    renderFilterTags('filter-provinces', d.provinces, 'province');
    renderFilterTags('filter-types', d.q_types, 'q_type');
    doSearch();
  });

document.getElementById('search-input').addEventListener('keydown', function(e) {
  if (e.key === 'Enter') { state.keyword = this.value.trim(); state.page = 1; doSearch(); }
});
document.getElementById('search-btn').addEventListener('click', function() {
  state.keyword = document.getElementById('search-input').value.trim();
  state.page = 1;
  doSearch();
});

function renderFilterTags(containerId, items, field) {
  var container = document.getElementById(containerId);
  items.forEach(function(item) {
    var tag = document.createElement('span');
    tag.className = 'filter-tag';
    tag.textContent = item.value + ' (' + item.count + ')';
    tag.addEventListener('click', function() {
      if (state[field] === item.value) {
        state[field] = null;
      } else {
        state[field] = item.value;
      }
      state.page = 1;
      updateSelectedDisplay();
      doSearch();
    });
    container.appendChild(tag);
  });
}

function updateSelectedDisplay() {
  var summary = document.getElementById('filter-summary');
  var tags = document.getElementById('selected-tags');
  var parts = [];
  if (state.year) parts.push(state.year + '年');
  if (state.province) parts.push(state.province);
  if (state.q_type) parts.push(state.q_type);
  if (parts.length > 0) {
    summary.style.display = 'block';
    tags.textContent = parts.join(' · ');
  } else {
    summary.style.display = 'none';
  }
}

function doSearch() {
  var params = 'page=' + state.page + '&size=' + state.size;
  if (state.keyword) params += '&keyword=' + encodeURIComponent(state.keyword);
  if (state.year) params += '&year=' + state.year;
  if (state.province) params += '&province=' + encodeURIComponent(state.province);
  if (state.q_type) params += '&q_type=' + encodeURIComponent(state.q_type);

  fetch('/api/questions?' + params)
    .then(function(r) { return r.json(); })
    .then(function(d) {
      if (d.error) { alert(d.error); return; }
      renderResults(d);
    });
}

function renderResults(data) {
  var container = document.getElementById('results-container');
  var pagination = document.getElementById('pagination');

  if (!data.questions || data.questions.length === 0) {
    container.innerHTML = '<div class="empty-state"><p>未找到匹配的题目</p></div>';
    pagination.innerHTML = '';
    document.getElementById('selected-count').textContent = '0';
    return;
  }

  document.getElementById('selected-count').textContent = data.total;

  var html = '<div class="result-count">共 ' + data.total + ' 条结果</div>';
  data.questions.forEach(function(q) {
    html += renderCard(q);
  });
  container.innerHTML = html;

  var totalPages = Math.ceil(data.total / data.size);
  if (totalPages > 1) {
    var ph = '<div class="pagination-bar"><span>每页</span>';
    ph += '<select onchange="changeSize(this.value)">';
    [15, 30, 50].forEach(function(s) {
      ph += '<option value="' + s + '"' + (state.size === s ? ' selected' : '') + '>' + s + '</option>';
    });
    ph += '</select><span>条</span>';
    ph += '<span class="page-info">共 ' + data.total + ' 条，第 ' + data.page + '/' + totalPages + ' 页</span>';
    ph += '<span class="page-btns">';
    for (var p = 1; p <= totalPages; p++) {
      if (p === data.page) {
        ph += '<span class="page-btn active">' + p + '</span>';
      } else {
        ph += '<span class="page-btn" onclick="goPage(' + p + ')">' + p + '</span>';
      }
    }
    ph += '</span></div>';
    pagination.innerHTML = ph;
  } else {
    pagination.innerHTML = '';
  }
}

function renderCard(q) {
  var badges = '';
  if (q.year) badges += '<span class="badge badge-year">' + q.year + '</span>';
  if (q.province) badges += '<span class="badge badge-prov">' + q.province + '</span>';
  if (q.q_type) badges += '<span class="badge badge-qtype">' + q.q_type + '</span>';

  var topicsHtml = '';
  if (q.topics) {
    q.topics.split(/\s+/).filter(Boolean).forEach(function(t) {
      topicsHtml += '<span class="topic-tag">' + escapeHtml(t) + '</span>';
    });
  }

  var stem = escapeHtml(q.stem || '');
  if (stem.length > 200) stem = stem.substring(0, 200) + '...';

  return '<div class="question-card" onclick="showDetail(\'' + q.id + '\')">'
    + '<div class="card-header"><span class="question-num">第' + q.question_num + '题</span><div class="badges">' + badges + '</div></div>'
    + '<div class="card-stem">' + stem + '</div>'
    + (topicsHtml ? '<div class="card-topics">' + topicsHtml + '</div>' : '')
    + '<div class="card-answer" onclick="event.stopPropagation()"><span class="answer-toggle" onclick="toggleAnswer(this)">▼ 查看答案</span><span class="answer-text" style="display:none">' + escapeHtml(q.answer || '') + '</span></div>'
    + '</div>';
}

function toggleAnswer(el) {
  var textEl = el.nextElementSibling;
  if (textEl.style.display === 'none') {
    textEl.style.display = 'inline';
    el.textContent = '▲ 隐藏答案';
  } else {
    textEl.style.display = 'none';
    el.textContent = '▼ 查看答案';
  }
}

function goPage(p) { state.page = p; doSearch(); window.scrollTo(0, 0); }
function changeSize(s) { state.size = parseInt(s); state.page = 1; doSearch(); }

function showDetail(qId) {
  fetch('/api/question/' + qId)
    .then(function(r) { return r.json(); })
    .then(function(q) {
      var html = '<h2>第' + q.question_num + '题 <small>' + (q.q_type || '') + '</small></h2>';
      html += '<div class="detail-meta">' + q.year + '年 ' + q.province + ' ' + q.paper_type + '</div>';
      html += '<div class="detail-stem">' + escapeHtml(q.stem || '') + '</div>';
      if (q.options && q.options.length) {
        html += '<div class="detail-options"><ul>';
        q.options.forEach(function(o) {
          for (var k in o) { html += '<li><strong>' + k + '.</strong> ' + escapeHtml(o[k]) + '</li>'; }
        });
        html += '</ul></div>';
      }
      html += '<div class="detail-section"><h3>答案</h3><p>' + escapeHtml(q.answer || '') + '</p></div>';
      if (q.explanation) html += '<div class="detail-section"><h3>解析</h3><p>' + escapeHtml(q.explanation) + '</p></div>';
      if (q.topics) html += '<div class="detail-section"><h3>知识点</h3><p>' + escapeHtml(q.topics) + '</p></div>';
      document.getElementById('modal-body').innerHTML = html;
      document.getElementById('detail-modal').style.display = 'flex';
    });
}

function closeModal() { document.getElementById('detail-modal').style.display = 'none'; }
document.getElementById('detail-modal').addEventListener('click', function(e) { if (e.target === this) closeModal(); });

function escapeHtml(str) {
  if (!str) return '';
  return str.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;').replace(/'/g,'&#39;');
}
```

- [ ] **Step 3: 更新 static/style.css — 保留原样式 + 新增**

在 `D:\Claude\gaokao-chem\static\style.css` 末尾追加：

```css
/* ── Base & Nav ── */
* { margin: 0; padding: 0; box-sizing: border-box; }
body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif; background: #0f0f1a; color: #ccc; min-height: 100vh; }

.top-nav { display: flex; justify-content: space-between; align-items: center; padding: 0 24px; height: 48px; background: #16162b; border-bottom: 1px solid #2a2a4a; }
.nav-left { display: flex; align-items: center; gap: 16px; }
.nav-logo { color: #7ecfff; font-weight: bold; font-size: 16px; text-decoration: none; }
.nav-right { display: flex; align-items: center; gap: 12px; font-size: 13px; }
.nav-link { color: #888; text-decoration: none; }
.nav-link:hover { color: #ccc; }
.nav-user { color: #ccc; }
.nav-badge { padding: 1px 8px; border-radius: 10px; font-size: 11px; }
.nav-badge.admin { background: #4a2a2a; color: #f48771; }
.nav-badge.vip { background: #2a4a2a; color: #7ecf9f; }
.nav-badge.trial { background: #2a2a4a; color: #7eaacf; }

/* ── Auth Pages ── */
.auth-page { display: flex; justify-content: center; align-items: center; min-height: 100vh; }
.auth-container { width: 360px; padding: 32px; background: #16162b; border: 1px solid #2a2a4a; border-radius: 8px; }
.auth-container h2 { color: #eee; margin-bottom: 24px; text-align: center; }
.auth-container label { display: block; font-size: 13px; color: #888; margin-bottom: 4px; margin-top: 12px; }
.auth-container input { width: 100%; padding: 10px 12px; background: #0f0f1a; border: 1px solid #3a3a5a; border-radius: 4px; color: #eee; font-size: 14px; }
.auth-container button { width: 100%; padding: 10px; margin-top: 20px; background: #4a6cf7; color: #fff; border: none; border-radius: 4px; font-size: 15px; cursor: pointer; }
.auth-container button:hover { background: #5a7cf7; }
.auth-switch { margin-top: 16px; text-align: center; font-size: 13px; color: #666; }
.auth-switch a { color: #7ecfff; }
.flash-error { padding: 8px 12px; background: #3a1a1a; border: 1px solid #6a3a3a; border-radius: 4px; color: #f48771; font-size: 13px; margin-bottom: 12px; }
.flash-ok { padding: 8px 12px; background: #1a3a1a; border: 1px solid #3a6a3a; border-radius: 4px; color: #7ecf9f; font-size: 13px; margin-bottom: 12px; }

/* ── Query Layout ── */
.query-layout { display: flex; min-height: calc(100vh - 48px); }
.query-sidebar { width: 260px; min-width: 260px; padding: 16px; background: #12121f; border-right: 1px solid #2a2a4a; overflow-y: auto; }
.query-sidebar h3 { color: #aaa; font-size: 14px; margin-bottom: 16px; }
.query-sidebar h4 { color: #888; font-size: 12px; margin: 12px 0 6px; text-transform: uppercase; letter-spacing: 1px; }
.filter-tags { display: flex; flex-wrap: wrap; gap: 4px; }
.filter-tag { background: #1a1a2e; color: #7eaacf; padding: 3px 8px; border-radius: 3px; font-size: 12px; cursor: pointer; border: 1px solid transparent; transition: all 0.15s; }
.filter-tag:hover { background: #2a2a4a; border-color: #4a6cf7; }
.filter-summary { margin-top: 16px; padding-top: 12px; border-top: 1px solid #2a2a4a; font-size: 12px; color: #666; }
.filter-summary span { color: #7ecfff; }

.query-main { flex: 1; padding: 16px 24px; overflow-y: auto; }
.search-bar { display: flex; gap: 8px; margin-bottom: 16px; }
.search-bar input { flex: 1; padding: 10px 14px; background: #1a1a2e; border: 1px solid #3a3a5a; border-radius: 6px; color: #eee; font-size: 14px; }
.search-bar input:focus { border-color: #4a6cf7; outline: none; }
.search-bar button { padding: 10px 20px; background: #4a6cf7; color: #fff; border: none; border-radius: 6px; cursor: pointer; font-size: 14px; }
.search-bar button:hover { background: #5a7cf7; }

/* ── Cards ── */
.question-card { padding: 14px; margin-bottom: 8px; background: #1a1a2e; border: 1px solid #2a2a4a; border-radius: 6px; cursor: pointer; transition: border-color 0.15s; }
.question-card:hover { border-color: #4a6cf7; }
.card-header { display: flex; align-items: center; gap: 8px; margin-bottom: 8px; }
.question-num { font-size: 12px; color: #666; }
.badges { display: flex; gap: 4px; flex-wrap: wrap; }
.badge { padding: 1px 6px; border-radius: 3px; font-size: 11px; }
.badge-year { background: #2a4a3a; color: #7ecf9f; }
.badge-prov { background: #2a3a4a; color: #7eaacf; }
.badge-qtype { background: #3a2a4a; color: #aa7ecf; }
.card-stem { font-size: 14px; line-height: 1.6; color: #bbb; margin-bottom: 8px; }
.card-topics { display: flex; gap: 4px; flex-wrap: wrap; margin-bottom: 6px; }
.topic-tag { background: #1a1a3e; color: #7ecfff; padding: 1px 6px; border-radius: 3px; font-size: 11px; cursor: pointer; }
.card-answer { font-size: 12px; color: #4a6cf7; cursor: pointer; }
.answer-text { color: #7ecf9f; }
.result-count { font-size: 13px; color: #666; margin-bottom: 12px; }
.empty-state { text-align: center; padding: 80px 0; color: #555; }
.empty-state p { margin-bottom: 8px; }

/* ── Pagination ── */
.pagination-bar { display: flex; align-items: center; gap: 8px; padding: 16px 0; border-top: 1px solid #2a2a4a; margin-top: 16px; font-size: 13px; color: #888; }
.pagination-bar select { padding: 4px 8px; background: #1a1a2e; color: #ccc; border: 1px solid #3a3a5a; border-radius: 3px; font-size: 12px; }
.page-info { margin: 0 8px; }
.page-btns { display: flex; gap: 4px; margin-left: auto; }
.page-btn { padding: 4px 10px; border-radius: 3px; font-size: 13px; cursor: pointer; background: #1a1a2e; color: #666; }
.page-btn.active { background: #2a2a5a; color: #7ecfff; }
.page-btn:hover:not(.active) { background: #2a2a4a; }

/* ── Modal ── */
.modal { position: fixed; inset: 0; background: rgba(0,0,0,0.7); display: flex; justify-content: center; align-items: center; z-index: 100; }
.modal-content { width: 700px; max-height: 80vh; overflow-y: auto; background: #16162b; border: 1px solid #2a2a4a; border-radius: 10px; padding: 24px; }
.modal-close { float: right; font-size: 24px; color: #666; cursor: pointer; }
.modal-close:hover { color: #ccc; }
.modal-content h2 { color: #eee; margin-bottom: 12px; }
.detail-meta { color: #888; font-size: 13px; margin-bottom: 12px; }
.detail-stem { color: #bbb; font-size: 15px; line-height: 1.8; margin-bottom: 16px; }
.detail-options ul { list-style: none; }
.detail-options li { color: #bbb; padding: 6px 0; font-size: 14px; }
.detail-section { margin-top: 16px; padding-top: 12px; border-top: 1px solid #2a2a4a; }
.detail-section h3 { color: #888; font-size: 13px; margin-bottom: 6px; }
.detail-section p { color: #bbb; font-size: 14px; line-height: 1.6; }

/* ── Admin Layout ── */
.admin-layout { display: flex; min-height: calc(100vh - 48px); }
.admin-sidebar { width: 200px; min-width: 200px; padding: 16px; background: #12121f; border-right: 1px solid #2a2a4a; }
.admin-sidebar h3 { color: #aaa; font-size: 13px; margin-bottom: 12px; }
.admin-sidebar a { display: block; padding: 6px 10px; color: #888; text-decoration: none; font-size: 14px; border-radius: 4px; margin-bottom: 2px; }
.admin-sidebar a.active, .admin-sidebar a:hover { background: #1a1a2e; color: #7ecfff; }
.admin-content { flex: 1; padding: 24px; }
.admin-content h2 { color: #eee; margin-bottom: 16px; }
.admin-content h2 small { font-size: 13px; color: #666; }
.admin-content label { display: block; font-size: 13px; color: #888; margin: 12px 0 4px; }
.admin-content input, .admin-content textarea, .admin-content select { width: 100%; padding: 8px 12px; background: #0f0f1a; border: 1px solid #3a3a5a; border-radius: 4px; color: #eee; font-size: 14px; }
.admin-content textarea { font-family: inherit; resize: vertical; }
.admin-content button { padding: 8px 20px; margin-top: 12px; background: #4a6cf7; color: #fff; border: none; border-radius: 4px; font-size: 14px; cursor: pointer; }
.admin-content button.danger { background: #7a3a3a; }
.admin-content button:hover { opacity: 0.9; }

.stats-grid { display: flex; gap: 16px; margin-bottom: 24px; }
.stat-card { padding: 20px; background: #1a1a2e; border: 1px solid #2a2a4a; border-radius: 8px; text-align: center; flex: 1; }
.stat-card h3 { font-size: 32px; color: #7ecfff; }
.stat-card p { font-size: 13px; color: #888; margin-top: 4px; }

.edit-card { padding: 16px; margin-bottom: 12px; background: #1a1a2e; border: 1px solid #2a2a4a; border-radius: 8px; }
.edit-card h3 { color: #ccc; font-size: 15px; margin-bottom: 8px; }
.edit-card label { margin: 6px 0 2px; font-size: 12px; }
.edit-card input, .edit-card textarea { width: 100%; padding: 6px 10px; margin-bottom: 4px; background: #0f0f1a; border: 1px solid #3a3a5a; border-radius: 3px; color: #ddd; font-size: 13px; }
.edit-card textarea { font-family: inherit; resize: vertical; }

.code-table { width: 100%; border-collapse: collapse; margin-top: 16px; font-size: 13px; }
.code-table th { text-align: left; padding: 8px 10px; background: #12121f; color: #888; font-weight: normal; border-bottom: 1px solid #2a2a4a; }
.code-table td { padding: 8px 10px; border-bottom: 1px solid #1a1a2e; }
.code-table code { color: #7ecfff; font-size: 12px; }
.badge-ok { color: #7ecf9f; }
.badge-used { color: #888; }
```

- [ ] **Step 4: Commit**

```bash
cd D:\Claude\gaokao-chem && git add templates/index.html static/app.js static/style.css && git commit -m "feat: redesign query page with left-right layout, add app.js and styles"
```

---

### Task 9: 应用入口组装

**Files:** `app.py`, `create_admin.py`

- [ ] **Step 1: 重写 app.py**

用以下内容重写 `D:\Claude\gaokao-chem\app.py`：

```python
from flask import Flask, render_template
from flask_login import LoginManager, current_user

from config import SECRET_KEY
from models import init_db, get_user_by_id

app = Flask(__name__)
app.secret_key = SECRET_KEY

login_manager = LoginManager()
login_manager.login_view = 'auth.login'
login_manager.init_app(app)


@login_manager.user_loader
def load_user(user_id):
    from auth import User
    user = get_user_by_id(user_id)
    return User(user) if user else None


@app.route('/')
def index():
    return render_template('index.html')


# Register blueprints
from auth import auth_bp
from vip import vip_bp
from query_bp import query_bp
from admin_bp import admin_bp

app.register_blueprint(auth_bp)
app.register_blueprint(vip_bp)
app.register_blueprint(query_bp)
app.register_blueprint(admin_bp)


if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=5001, debug=True)
```

- [ ] **Step 2: 创建 create_admin.py**

写入 `D:\Claude\gaokao-chem\create_admin.py`：

```python
"""CLI script to create an admin user."""
import sys
from models import init_db, create_user

if len(sys.argv) < 3:
    print('Usage: python create_admin.py <username> <password>')
    sys.exit(1)

init_db()
username = sys.argv[1]
password = sys.argv[2]
create_user(username, password, is_admin=1)
print(f'Admin user "{username}" created.')
```

- [ ] **Step 3: 启动验证**

```bash
cd D:\Claude\gaokao-chem && python -c "from app import app; print('App loads OK')"
```

- [ ] **Step 4: Commit**

```bash
cd D:\Claude\gaokao-chem && git add app.py create_admin.py && git commit -m "feat: wire up app entry point with all blueprints"
```

---

### Task 10: 清理旧代码

**Files:** 删除多个不再需要的文件

- [ ] **Step 1: 删除爬虫和导入脚本**

```bash
cd D:\Claude\gaokao-chem && rm -rf crawler/ discover_papers.py fetch_paper.py batch_fetch.py import_from_hf.py pipeline.py check_content.py import_pdf.py paper_urls.json paper_urls_full.json paper_urls_good.json
```

- [ ] **Step 2: 验证应用仍能加载**

```bash
cd D:\Claude\gaokao-chem && python -c "from app import app; print('OK')"
```

- [ ] **Step 3: Commit**

```bash
cd D:\Claude\gaokao-chem && git add -A && git commit -m "chore: remove crawler and old import scripts"
```

---

### Task 11: 初始化管理员账号

- [ ] **Step 1: 创建管理员**

```bash
cd D:\Claude\gaokao-chem && python create_admin.py wangjiang <your-password>
```

---

### Task 12: 验证清单

- [ ] 启动应用：`python app.py`
- [ ] 访问 http://localhost:5001 → 跳转到登录页
- [ ] 注册一个普通账号 → 进入查询页，看到左右分栏
- [ ] 试用期内可以查询题目
- [ ] 管理员登录 → 导航栏显示"后台"链接
- [ ] 管理后台 → 上传 PDF → AI 解析 → 审核入库
- [ ] 管理后台 → 生成激活码
- [ ] 普通用户 → 使用激活码充值 → VIP 延期
