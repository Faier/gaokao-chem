from flask import Flask, render_template, request, jsonify

from models import init_db, get_question, get_paper, get_paper_questions, get_all_papers, get_stats, get_filter_options
from search import search_keyword, search_semantic

app = Flask(__name__)


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/search')
def api_search():
    q = request.args.get('q', '').strip()
    page = request.args.get('page', 1, type=int)
    size = request.args.get('size', 20, type=int)
    year = request.args.get('year', type=int)
    province = request.args.get('province', '').strip() or None
    q_type = request.args.get('q_type', '').strip() or None

    result = search_keyword(q, page=page, size=size,
                            year=year, province=province, q_type=q_type)
    return jsonify(result)


@app.route('/api/search/semantic')
def api_search_semantic():
    q = request.args.get('q', '').strip()
    top_k = request.args.get('top_k', 10, type=int)
    result = search_semantic(q, top_k=top_k)
    return jsonify(result)


@app.route('/api/question/<q_id>')
def api_question(q_id):
    question = get_question(q_id)
    if not question:
        return jsonify({'error': 'not found'}), 404
    import json
    try:
        question['options'] = json.loads(question['options']) if question.get('options') else []
    except (json.JSONDecodeError, TypeError):
        question['options'] = []
    paper = get_paper(question['paper_id'])
    question['paper'] = paper
    return jsonify(question)


@app.route('/api/papers')
def api_papers():
    year = request.args.get('year', type=int)
    province = request.args.get('province', '').strip() or None
    papers = get_all_papers(year=year, province=province)
    return jsonify({'papers': papers})


@app.route('/api/paper/<paper_id>')
def api_paper_detail(paper_id):
    paper = get_paper(paper_id)
    if not paper:
        return jsonify({'error': 'not found'}), 404
    questions = get_paper_questions(paper_id)
    import json
    for q in questions:
        try:
            q['options'] = json.loads(q['options']) if q.get('options') else []
        except (json.JSONDecodeError, TypeError):
            q['options'] = []
    paper['questions'] = questions
    return jsonify(paper)


@app.route('/api/stats')
def api_stats():
    stats = get_stats()
    stats.update(get_filter_options())
    return jsonify(stats)


if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=5001, debug=True)
