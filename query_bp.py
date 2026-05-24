import json
from functools import wraps
from flask import Blueprint, jsonify, request
from flask_login import login_required, current_user

from models import get_question, get_paper, get_filter_counts
from search import search_questions

query_bp = Blueprint('query', __name__, url_prefix='/api')


def vip_required(f):
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
