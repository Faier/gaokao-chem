import json
import os
from flask import Blueprint, render_template, request, jsonify
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
