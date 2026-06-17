import json
import os
from flask import Blueprint, render_template, request, jsonify, current_app, send_from_directory
from flask_login import login_required, current_user
from functools import wraps
from concurrent.futures import ThreadPoolExecutor

from models import (
    insert_paper, insert_question, get_paper, get_paper_questions,
    get_all_papers, update_paper_status, delete_paper,
    insert_question_image, get_question_images,
    generate_codes, get_all_codes, get_stats, get_db
)
from parser import (
    call_mimo,
    extract_text_from_document,
    get_document_kind,
    parse_document_to_questions,
    save_images_to_disk,
)
from config import UPLOAD_DIR, DATA_DIR

executor = ThreadPoolExecutor(max_workers=4)


def async_parse_task(app, paper_id, filepath):
    with app.app_context():
        try:
            update_paper_status(paper_id, 'parsing')
            result = parse_document_to_questions(filepath)
            conn = get_db()
            if 'error' not in result:
                conn.execute(
                    "UPDATE papers SET parse_result=?, status='parsed' WHERE id=?",
                    (json.dumps(result, ensure_ascii=False), paper_id)
                )
            else:
                conn.execute(
                    "UPDATE papers SET parse_result=?, status='failed' WHERE id=?",
                    (json.dumps(result, ensure_ascii=False), paper_id)
                )
            conn.commit()
        except Exception as e:
            try:
                conn = get_db()
                conn.execute(
                    "UPDATE papers SET parse_result=?, status='failed' WHERE id=?",
                    (json.dumps({"error": f"后台解析异常: {str(e)}"}, ensure_ascii=False), paper_id)
                )
                conn.commit()
            except Exception:
                pass

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')


def parse_filename(name):
    """Extract year, province, paper_type, title from filename.

    Examples:
      2024年全国卷理综化学.pdf → year=2024, province=全国卷, type=理综, title=2024年高考全国卷理综化学
      2023北京化学高考真题.pdf → year=2023, province=北京, type=化学
      2022年上海卷化学.pdf       → year=2022, province=上海, type=化学
    """
    import re

    # Strip extension
    base = name.rsplit('.', 1)[0].strip()

    year = ''
    province = ''
    paper_type = ''

    # Extract year: 4-digit starting with 19/20
    m = re.search(r'(20\d{2})', base)
    if m:
        year = m.group(1)

    # Extract province
    province_map = [
        '全国卷', '全国', '新课标', '北京', '上海', '天津', '重庆',
        '浙江', '江苏', '广东', '山东', '湖北', '湖南', '河北',
        '河南', '四川', '福建', '安徽', '江西', '辽宁', '陕西',
        '山西', '吉林', '黑龙江', '广西', '云南', '贵州', '甘肃',
        '内蒙古', '新疆', '西藏', '海南', '宁夏', '青海',
    ]
    for p in sorted(province_map, key=len, reverse=True):
        if p in base:
            province = p
            if province == '全国':
                province = '全国卷'
            break

    # Extract paper type
    type_map = ['理综', '文综', '化学', '物理', '生物', '新高考']
    for t in type_map:
        if t in base:
            paper_type = t
            break

    if not paper_type:
        paper_type = '化学'

    # Build title
    title = f'{year}年高考{province}{paper_type}' if year and province else base

    return {
        'year': year,
        'province': province,
        'paper_type': paper_type,
        'title': title,
    }


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
    """Step 1: Upload document, parse filename, AI fallback for metadata."""
    file = request.files.get('document') or request.files.get('pdf')
    if not file:
        return jsonify({'ok': False, 'msg': '请选择 PDF、DOC 或 DOCX 文件'}), 400

    from werkzeug.utils import secure_filename
    filename = secure_filename(file.filename or 'upload.pdf') or 'upload.pdf'
    if not get_document_kind(filename):
        return jsonify({'ok': False, 'msg': '仅支持 PDF、DOC、DOCX 文档'}), 400

    filepath = os.path.join(UPLOAD_DIR, filename)
    file.save(filepath)

    # 1. Try filename parsing first
    meta = parse_filename(filename)

    # 2. If filename didn't give good results, try AI
    if not meta['year'] or not meta['province']:
        text = extract_text_from_document(filepath)
        if text:
            result = call_mimo(text[:3000], system_prompt=METADATA_PROMPT)
            if result and 'year' in result:
                meta['year'] = meta['year'] or str(result.get('year', ''))
                meta['province'] = meta['province'] or str(result.get('province', ''))
                meta['paper_type'] = meta['paper_type'] or str(result.get('paper_type', ''))
                meta['title'] = str(result.get('title', meta['title']))
            text_preview = text[:500]
        else:
            text_preview = ''
    else:
        # Filename parsed successfully - still extract text for preview
        text = extract_text_from_document(filepath)
        text_preview = text[:500] if text else '（文字提取失败，但文件名已识别）'

    if not meta['year']:
        os.remove(filepath)
        return jsonify({'ok': False, 'msg': '无法从文件名或内容中识别年份，请确保文件名包含年份（如2024）'}), 400

    return jsonify({
        'ok': True,
        'filename': filename,
        'filepath': filepath,
        'text_preview': text_preview,
        'meta': meta,
        'source': 'filename' if meta['province'] else 'ai',
    })


@admin_bp.route('/upload/confirm', methods=['POST'])
@admin_required
def upload_confirm():
    """Step 2: Save paper with user-confirmed metadata, then start async parsing task."""
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

    # Start async parse task
    app = current_app._get_current_object()
    executor.submit(async_parse_task, app, paper_id, filepath)

    return jsonify({'ok': True, 'paper_id': paper_id, 'msg': '试卷信息已确认，后台 AI 正在解析中...'})


@admin_bp.route('/paper/<paper_id>/status')
@admin_required
def paper_status(paper_id):
    paper = get_paper(paper_id)
    if not paper:
        return jsonify({'error': 'not found'}), 404
    return jsonify({
        'ok': True,
        'status': paper.get('status', 'pending'),
        'has_result': bool(paper.get('parse_result'))
    })


@admin_bp.route('/review/<paper_id>')
@admin_required
def review(paper_id):
    """Show parsed questions for review. Reads from stored parse_result."""
    paper = get_paper(paper_id)
    if not paper:
        return '试卷不存在', 404

    questions = []
    error = None

    if paper.get('status') == 'failed':
        if paper.get('parse_result'):
            try:
                res = json.loads(paper['parse_result'])
                error = res.get('error', '解析失败，未获得有效结果')
            except Exception:
                error = '解析失败且数据异常'
        else:
            error = '解析失败'
    elif paper.get('status') in ['parsed', 'confirmed']:
        if paper.get('parse_result'):
            try:
                parsed = json.loads(paper['parse_result'])
                questions = parsed.get('questions', []) if isinstance(parsed, dict) else parsed
            except json.JSONDecodeError:
                error = '解析结果数据损坏'
        else:
            error = '解析已完成，但无结果数据'

    return render_template('admin/review.html', paper=paper, questions=questions, error=error)


@admin_bp.route('/review/<paper_id>/reparse', methods=['POST'])
@admin_required
def review_reparse(paper_id):
    """Force re-parse paper questions asynchronously."""
    paper = get_paper(paper_id)
    if not paper:
        return jsonify({'error': 'not found'}), 404

    # Reset status and clear old result
    conn = get_db()
    conn.execute("UPDATE papers SET parse_result=NULL, status='pending' WHERE id=?", (paper_id,))
    conn.commit()

    app = current_app._get_current_object()
    executor.submit(async_parse_task, app, paper_id, paper['file_path'])

    return jsonify({'ok': True, 'msg': '已重新提交解析任务，请等待后台完成...'})


@admin_bp.route('/review/<paper_id>/confirm', methods=['POST'])
@admin_required
def review_confirm(paper_id):
    """Insert edited questions into DB."""
    paper = get_paper(paper_id)
    if not paper:
        return jsonify({'error': 'not found'}), 404

    data = request.get_json()
    questions = data.get('questions', [])
    parsed = {}
    if paper.get('parse_result'):
        try:
            parsed = json.loads(paper['parse_result'])
        except json.JSONDecodeError:
            parsed = {}
    saved_images = save_images_to_disk(
        parsed.get('images', []),
        paper_id,
        os.path.join(DATA_DIR, 'images'),
    )
    image_paths_by_seq = {seq: path for seq, path in saved_images}

    for q in questions:
        options_json = json.dumps(q.get('options', []), ensure_ascii=False)
        question_id = insert_question(
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
        seen_refs = set()
        for ref in q.get('image_refs') or []:
            if not isinstance(ref, int) or ref in seen_refs or ref not in image_paths_by_seq:
                continue
            seen_refs.add(ref)
            insert_question_image(question_id, paper_id, ref, image_paths_by_seq[ref])

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
