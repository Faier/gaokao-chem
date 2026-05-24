"""Keyword search with jieba tokenization for Chinese text."""

import json
import jieba
from models import get_db

jieba.setLogLevel(20)


def search_questions(keyword='', page=1, size=15, year=None, province=None, q_type=None):
    """Paginated question search with jieba-tokenized LIKE matching and filters."""
    conn = get_db()

    where_parts = []
    params = []

    if keyword and keyword.strip():
        tokens = [t.strip() for t in jieba.cut(keyword) if len(t.strip()) >= 1]
        if tokens:
            like_parts = []
            for token in tokens:
                like_parts.append(
                    "(q.stem LIKE ? OR q.answer LIKE ? OR q.explanation LIKE ? OR q.topics LIKE ?)"
                )
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
