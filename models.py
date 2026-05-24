import sqlite3
import uuid
import jieba
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash, check_password_hash

from config import DB_PATH, TRIAL_HOURS

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


def update_paper_file(paper_id, file_path, file_size=None, page_count=None):
    conn = get_db()
    conn.execute("""
        UPDATE papers SET file_path=?, file_size=?, page_count=?
        WHERE id=?
    """, (file_path, file_size, page_count, paper_id))
    conn.commit()
    conn.close()


def delete_paper(paper_id):
    conn = get_db()
    conn.execute("DELETE FROM questions WHERE paper_id=?", (paper_id,))
    conn.execute("DELETE FROM papers WHERE id=?", (paper_id,))
    conn.commit()
    conn.close()


# ── Question helpers ──

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
        if datetime.strptime(user['vip_expire_at'], '%Y-%m-%d %H:%M:%S') > datetime.now():
            return True
    if user.get('trial_start'):
        trial_start = datetime.strptime(user['trial_start'], '%Y-%m-%d %H:%M:%S')
        if datetime.now() - trial_start < timedelta(hours=TRIAL_HOURS):
            return True
    return False


def get_trial_remaining(user):
    """Return remaining trial hours, or 0 if expired."""
    trial_start = datetime.strptime(user['trial_start'], '%Y-%m-%d %H:%M:%S')
    elapsed = datetime.now() - trial_start
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

    now = datetime.now()
    if user.get('vip_expire_at'):
        current_expire = datetime.strptime(user['vip_expire_at'], '%Y-%m-%d %H:%M:%S')
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
