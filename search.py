"""Keyword search via SQLite FTS5 with LIKE fallback for Chinese text."""

from models import get_db


def _like_search(conn, q, page, size, year, province, q_type):
    """Fallback LIKE-based search. Used when FTS5 returns 0 results."""
    like_pattern = '%' + q.strip().replace('%', '\\%') + '%'
    params = [like_pattern, like_pattern, like_pattern, like_pattern]

    where_sql = ""
    if year:
        where_sql += " AND q.year = ?"
        params.append(int(year))
    if province:
        where_sql += " AND q.province = ?"
        params.append(province)
    if q_type:
        where_sql += " AND q.q_type = ?"
        params.append(q_type)

    count_sql = f"""
        SELECT COUNT(*) FROM questions q
        WHERE (q.stem LIKE ? OR q.answer LIKE ? OR q.explanation LIKE ? OR q.topics LIKE ?)
        {where_sql}
    """
    total = conn.execute(count_sql, params).fetchone()[0]

    offset = (page - 1) * size
    query_sql = f"""
        SELECT * FROM questions q
        WHERE (q.stem LIKE ? OR q.answer LIKE ? OR q.explanation LIKE ? OR q.topics LIKE ?)
        {where_sql}
        ORDER BY q.year DESC LIMIT ? OFFSET ?
    """
    rows = conn.execute(query_sql, params + [size, offset]).fetchall()
    return total, rows


def search_keyword(q, page=1, size=20, year=None, province=None, q_type=None):
    """Full-text search with optional filters.

    Tries FTS5 first; falls back to LIKE search when FTS5 returns 0 results
    (common for Chinese text since unicode61 tokenizer treats each CJK
    character as a separate token).
    """
    if not q or not q.strip():
        return {'total': 0, 'page': page, 'size': size, 'questions': []}

    conn = get_db()

    where_clauses = []
    params = []
    if year:
        where_clauses.append("q.year = ?")
        params.append(int(year))
    if province:
        where_clauses.append("q.province = ?")
        params.append(province)
    if q_type:
        where_clauses.append("q.q_type = ?")
        params.append(q_type)

    where_sql = ''
    if where_clauses:
        where_sql = ' AND ' + ' AND '.join(where_clauses)

    # Try FTS5 first
    total = 0
    rows = []
    terms = q.strip().split()
    fts_query = ' AND '.join(terms)

    try:
        count_sql = f"""
            SELECT COUNT(*) FROM questions_fts f
            JOIN questions q ON q.rowid = f.rowid
            WHERE questions_fts MATCH ?{where_sql}
        """
        total = conn.execute(count_sql, [fts_query] + params).fetchone()[0]
    except Exception:
        total = 0

    if total > 0:
        offset = (page - 1) * size
        try:
            query_sql = f"""
                SELECT q.* FROM questions_fts f
                JOIN questions q ON q.rowid = f.rowid
                WHERE questions_fts MATCH ?{where_sql}
                ORDER BY rank
                LIMIT ? OFFSET ?
            """
            rows = conn.execute(query_sql, [fts_query] + params + [size, offset]).fetchall()
        except Exception:
            total = 0

    # Fall back to LIKE if FTS5 found nothing
    if total == 0:
        total, rows = _like_search(conn, q, page, size, year, province, q_type)

    conn.close()

    questions = []
    for row in rows:
        qd = dict(row)
        import json
        try:
            qd['options'] = json.loads(qd['options']) if qd.get('options') else []
        except (json.JSONDecodeError, TypeError):
            qd['options'] = []
        questions.append(qd)

    return {
        'total': total,
        'page': page,
        'size': size,
        'questions': questions
    }


def search_semantic(q, top_k=10):
    """Semantic search stub — falls back to keyword search for MVP."""
    result = search_keyword(q, page=1, size=top_k)
    if result['questions']:
        result['scores'] = [1.0 - i * 0.05 for i in range(len(result['questions']))]
    else:
        result['scores'] = []
    return result
