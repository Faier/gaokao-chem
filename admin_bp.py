import json
import os
from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required, current_user
from functools import wraps

from models import (
    insert_paper, insert_question, get_paper, get_paper_questions,
    get_all_papers, update_paper_status, delete_paper,
    generate_codes, get_all_codes, get_stats, get_db
)
from parser import parse_pdf_to_questions, extract_text_from_pdf, call_deepseek
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


METADATA_PROMPT = """分析以下高考化学试卷文本，提取以下字段并以JSON返回：
- year: 年份（整数，如2024）
- province: 省份或卷型（如"全国卷"、"北京"、"上海"）
- paper_type: 试卷类型（如"理综"、"化学"）
- title: 试卷标题（如"2024年高考全国卷理综化学"）

只返回JSON，不要其他内容：
```json
{"year": 2024, "province": "全国卷", "paper_type": "理综", "title": "2024年高考全国卷理综化学"}
```"""


@admin_bp.route('/')
@admin_required
def index():
    stats = get_stats()
    pending = get_all_papers(status='pending')
    return render_template('admin/index.html', stats=stats, pending=pending)


@admin_bp.route('/upload', methods=['GET'])
@admin_required
def upload_page():
    return render_template('admin/upload.html')


@admin_bp.route('/upload/analyze', methods=['POST'])
@admin_required
def upload_analyze():
    """Step 1: Upload PDF, extract text, auto-detect metadata via AI."""
    file = request.files.get('pdf')
    if not file:
        return jsonify({'ok': False, 'msg': '请选择 PDF 文件'}), 400

    # Save temp file
    filename = file.filename or 'upload.pdf'
    filepath = os.path.join(UPLOAD_DIR, filename)
    file.save(filepath)

    # Extract text from first few pages
    text = extract_text_from_pdf(filepath)
    if not text:
        os.remove(filepath)
        return jsonify({'ok': False, 'msg': 'PDF 文字提取失败，文件可能为扫描件'}), 400

    # Use AI to detect metadata (send first 3000 chars)
    meta = {'year': '', 'province': '', 'paper_type': '', 'title': ''}
    result = call_deepseek(METADATA_PROMPT, text[:3000])
    if result and 'year' in result:
        meta = {
            'year': str(result.get('year', '')),
            'province': str(result.get('province', '')),
            'paper_type': str(result.get('paper_type', '')),
            'title': str(result.get('title', '')),
        }

    return jsonify({
        'ok': True,
        'filename': filename,
        'filepath': filepath,
        'text_preview': text[:500],
        'meta': meta,
    })


@admin_bp.route('/upload/confirm', methods=['POST'])
@admin_required
def upload_confirm():
    """Step 2: Save paper with user-confirmed metadata, then parse questions."""
    year = request.form.get('year', type=int)
    province = request.form.get('province', '').strip()
    paper_type = request.form.get('paper_type', '').strip()
    title = request.form.get('title', '').strip()
    filepath = request.form.get('filepath', '').strip()

    if not all([year, province, paper_type, title, filepath]):
        return jsonify({'ok': False, 'msg': '请填写所有字段'}), 400
    if not os.path.exists(filepath):
        return jsonify({'ok': False, 'msg': '文件已丢失，请重新上传'}), 400

    paper_id = insert_paper(
        year=year, province=province, paper_type=paper_type,
        title=title, file_path=filepath,
        file_size=os.path.getsize(filepath)
    )

    # Parse questions via AI
    result = parse_pdf_to_questions(filepath)
    if 'error' not in result:
        # Store parse result in DB for review page
        conn = get_db()
        conn.execute(
            "UPDATE papers SET parse_result=? WHERE id=?",
            (json.dumps(result['questions'], ensure_ascii=False), paper_id)
        )
        conn.commit()
        conn.close()

    return jsonify({'ok': True, 'paper_id': paper_id, 'msg': '上传成功，正在解析...'})


@admin_bp.route('/review/<paper_id>')
@admin_required
def review(paper_id):
    """Show parsed questions for review. Reads from stored parse_result."""
    paper = get_paper(paper_id)
    if not paper:
        return '试卷不存在', 404

    questions = []
    error = None

    if paper.get('parse_result'):
        try:
            questions = json.loads(paper['parse_result'])
        except json.JSONDecodeError:
            error = '解析结果数据损坏'

    if not questions and not error:
        # Parse hasn't happened yet, or failed — try now
        result = parse_pdf_to_questions(paper['file_path'])
        if 'error' in result:
            error = result['error']
        else:
            questions = result.get('questions', [])
            # Store for next time
            conn = get_db()
            conn.execute(
                "UPDATE papers SET parse_result=? WHERE id=?",
                (json.dumps(questions, ensure_ascii=False), paper_id)
            )
            conn.commit()
            conn.close()

    return render_template('admin/review.html', paper=paper, questions=questions, error=error)


@admin_bp.route('/review/<paper_id>/reparse', methods=['POST'])
@admin_required
def review_reparse(paper_id):
    """Force re-parse paper questions (discards existing parse result)."""
    paper = get_paper(paper_id)
    if not paper:
        return jsonify({'error': 'not found'}), 404

    result = parse_pdf_to_questions(paper['file_path'])
    if 'error' in result:
        return jsonify({'ok': False, 'msg': result['error']}), 500

    questions = result.get('questions', [])
    conn = get_db()
    conn.execute(
        "UPDATE papers SET parse_result=? WHERE id=?",
        (json.dumps(questions, ensure_ascii=False), paper_id)
    )
    conn.commit()
    conn.close()
    return jsonify({'ok': True, 'msg': f'重新解析完成，{len(questions)} 道题目'})


@admin_bp.route('/review/<paper_id>/confirm', methods=['POST'])
@admin_required
def review_confirm(paper_id):
    """Insert edited questions into DB."""
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


@admin_bp.route('/review/<paper_id>/delete', methods=['POST'])
@admin_required
def review_delete(paper_id):
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
