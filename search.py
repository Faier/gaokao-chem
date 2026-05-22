"""Keyword search via SQLite FTS5 with filter support."""

from models import get_db


def search_keyword(q, page=1, size=20, year=None, province=None, q_type=None):
    """Full-text search with optional filters.

    Args:
        q: Search query string
        page: Page number (1-indexed)
        size: Results per page
        year: Filter by exam year
        province: Filter by province
        q_type: Filter by question type

    Returns:
        {total, page, size, questions: [...]}
    """
    if not q or not q.strip():
        return {'total': 0, 'page': page, 'size': size, 'questions': []}

    conn = get_db()

    # Build FTS5 query — escape special chars and wrap each term
    terms = q.strip().split()
    fts_query = ' AND '.join(terms)

    # Count total matches
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

    try:
        count_sql = f"""
            SELECT COUNT(*) FROM questions_fts f
            JOIN questions q ON q.rowid = f.rowid
            WHERE questions_fts MATCH ?{where_sql}
        """
        total = conn.execute(count_sql, [fts_query] + params).fetchone()[0]
    except Exception:
        # FTS5 may error on special chars; fallback to LIKE search
        like_pattern = '%' + q.strip().replace('%', '\\%') + '%'
        count_sql = f"""
            SELECT COUNT(*) FROM questions q
            WHERE (q.stem LIKE ? OR q.answer LIKE ? OR q.explanation LIKE ? OR q.topics LIKE ?)
        """
        if year:
            count_sql += " AND q.year = ?"
        if province:
            count_sql += " AND q.province = ?"
        if q_type:
            count_sql += " AND q.q_type = ?"
        total = conn.execute(
            count_sql,
            [like_pattern, like_pattern, like_pattern, like_pattern] + params
        ).fetchone()[0]

    # Fetch page
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
        like_pattern = '%' + q.strip().replace('%', '\\%') + '%'
        query_sql = f"""
            SELECT * FROM questions q
            WHERE (q.stem LIKE ? OR q.answer LIKE ? OR q.explanation LIKE ? OR q.topics LIKE ?)
        """
        if year:
            query_sql += " AND q.year = ?"
        if province:
            query_sql += " AND q.province = ?"
        if q_type:
            query_sql += " AND q.q_type = ?"
        query_sql += " ORDER BY q.year DESC LIMIT ? OFFSET ?"
        rows = conn.execute(
            query_sql,
            [like_pattern, like_pattern, like_pattern, like_pattern] + params + [size, offset]
        ).fetchall()

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
