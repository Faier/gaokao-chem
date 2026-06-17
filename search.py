import re
import json
import jieba
from models import get_db

jieba.setLogLevel(20)


def search_questions(keyword='', page=1, size=15, year=None, province=None, q_type=None):
    """Paginated question search with jieba-tokenized FTS5 MATCH and filters."""
    conn = get_db()

    where_parts = []
    params = []

    if keyword and keyword.strip():
        tokens = [t.strip() for t in jieba.cut(keyword) if len(t.strip()) >= 1]
        clean_tokens = []
        for t in tokens:
            cleaned = re.sub(r'[^\w]', '', t)
            if cleaned:
                clean_tokens.append(cleaned)
        if clean_tokens:
            fts_query = " ".join(clean_tokens)
            where_parts.append("q.rowid IN (SELECT rowid FROM questions_fts WHERE questions_fts MATCH ?)")
            params.append(fts_query)

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
