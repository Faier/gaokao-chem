import sqlite3
import uuid
from datetime import datetime

from config import DB_PATH


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

        CREATE VIRTUAL TABLE IF NOT EXISTS questions_fts USING fts5(
            stem,
            answer,
            explanation,
            topics,
            content='questions',
            content_rowid='rowid',
            tokenize='porter unicode61'
        );

        CREATE TRIGGER IF NOT EXISTS questions_ai AFTER INSERT ON questions BEGIN
            INSERT INTO questions_fts(rowid, stem, answer, explanation, topics)
            VALUES (new.rowid, new.stem, new.answer, new.explanation, new.topics);
        END;

        CREATE TRIGGER IF NOT EXISTS questions_ad AFTER DELETE ON questions BEGIN
            INSERT INTO questions_fts(questions_fts, rowid, stem, answer, explanation, topics)
            VALUES ('delete', old.rowid, old.stem, old.answer, old.explanation, old.topics);
        END;

        CREATE TRIGGER IF NOT EXISTS questions_au AFTER UPDATE ON questions BEGIN
            INSERT INTO questions_fts(questions_fts, rowid, stem, answer, explanation, topics)
            VALUES ('delete', old.rowid, old.stem, old.answer, old.explanation, old.topics);
            INSERT INTO questions_fts(rowid, stem, answer, explanation, topics)
            VALUES (new.rowid, new.stem, new.answer, new.explanation, new.topics);
        END;
    """)
    conn.commit()
    conn.close()


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


def get_paper(paper_id):
    conn = get_db()
    row = conn.execute("SELECT * FROM papers WHERE id = ?", (paper_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


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


def get_all_papers(year=None, province=None):
    conn = get_db()
    q = "SELECT * FROM papers WHERE 1=1"
    params = []
    if year:
        q += " AND year = ?"
        params.append(year)
    if province:
        q += " AND province = ?"
        params.append(province)
    q += " ORDER BY year DESC, province"
    rows = conn.execute(q, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_stats():
    conn = get_db()
    total_q = conn.execute("SELECT COUNT(*) FROM questions").fetchone()[0]
    total_p = conn.execute("SELECT COUNT(*) FROM papers").fetchone()[0]
    years = conn.execute(
        "SELECT MIN(year), MAX(year) FROM questions"
    ).fetchone()
    conn.close()
    return {
        'total_questions': total_q,
        'total_papers': total_p,
        'year_min': years[0],
        'year_max': years[1]
    }


def get_filter_options():
    """Return distinct years, provinces, and question types for filter dropdowns."""
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


def update_paper_file(paper_id, file_path, file_size=None, page_count=None):
    conn = get_db()
    conn.execute("""
        UPDATE papers SET file_path=?, file_size=?, page_count=?
        WHERE id=?
    """, (file_path, file_size, page_count, paper_id))
    conn.commit()
    conn.close()


def paper_exists(year, province, paper_type):
    """Check if a paper is already in the database."""
    conn = get_db()
    row = conn.execute(
        "SELECT id FROM papers WHERE year=? AND province=? AND paper_type=?",
        (year, province, paper_type)
    ).fetchone()
    conn.close()
    return bool(row)
