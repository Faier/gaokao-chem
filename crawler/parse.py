"""Use DeepSeek API to parse exam paper content into structured questions.

For each paper, extract the full text (from PDF or HTML), send to the AI
with a structured extraction prompt, parse the JSON response, and insert
each question into the database.
"""

import json
import re
import os
import requests

from config import DEEPSEEK_API_KEY, DEEPSEEK_API_URL, DEEPSEEK_MODEL, PAPERS_DIR
from models import get_db, get_paper, insert_question, update_paper_file, get_paper_questions

# Attempt to import PDF readers
try:
    import pdfplumber
    HAS_PDFPLUMBER = True
except ImportError:
    HAS_PDFPLUMBER = False

try:
    import PyPDF2
    HAS_PYPDF2 = True
except ImportError:
    HAS_PYPDF2 = False


EXTRACTION_PROMPT = """你是一个高考化学试卷解析专家。请将以下试卷内容解析为结构化的题目列表。

一份标准的高考化学试卷通常包含 10-15 道题目（7道选择题+3道必做大题+2道选做题）。
请只提取真正的考试题目，不要提取：试卷说明、答题须知、评分标准、目录、页眉页脚等非题目内容。

对于每道题目，提取以下字段并以 JSON 数组格式返回：
- question_num: 题号（整数）
- q_type: 题型，只能是 "选择题" / "填空题" / "实验题" / "计算题" / "简答题" 之一
- stem: 题干原文（完整保留，包括化学方程式和符号）
- options: 选项列表，如 [{"A":"..."},{"B":"..."}]，选择题必有，其他题型为空数组
- answer: 标准答案
- explanation: 题目解析（如果有的话）
- topics: 涉及的知识点关键词，用空格分隔，如 "氧化还原反应 电化学 原电池"

重要：每道大题（如工艺流程题、实验题）应作为一个整体题目，不要将其拆分成多个小题。
一道大题下面的多个小问应该合并到 stem 字段中。

请严格按以下 JSON 格式返回，不要包含其他内容：
```json
{
  "questions": [
    {
      "question_num": 1,
      "q_type": "选择题",
      "stem": "...",
      "options": [{"A":"..."},{"B":"..."}],
      "answer": "B",
      "explanation": "...",
      "topics": "关键词1 关键词2"
    }
  ]
}
```"""


def _extract_text_from_pdf(filepath):
    """Extract text from a PDF file. Tries pdfplumber first, then PyPDF2."""
    text_parts = []

    if HAS_PDFPLUMBER:
        try:
            import pdfplumber
            with pdfplumber.open(filepath) as pdf:
                for page in pdf.pages:
                    t = page.extract_text()
                    if t:
                        text_parts.append(t)
            result = '\n\n'.join(text_parts)
            if result.strip():
                return result
        except Exception as e:
            print(f"[parse] pdfplumber failed for {filepath}: {e}")

    if HAS_PYPDF2:
        try:
            import PyPDF2
            with open(filepath, 'rb') as f:
                reader = PyPDF2.PdfReader(f)
                for page in reader.pages:
                    t = page.extract_text()
                    if t:
                        text_parts.append(t)
            result = '\n\n'.join(text_parts)
            if result.strip():
                return result
        except Exception as e:
            print(f"[parse] PyPDF2 failed for {filepath}: {e}")

    return None


def _call_deepseek(prompt, paper_text, retry=True):
    """Send extraction request to DeepSeek API, return parsed JSON or None.

    Retries once with a fix-prompt if the first parse fails due to JSON errors.
    """
    payload = {
        "model": DEEPSEEK_MODEL,
        "messages": [
            {"role": "system", "content": prompt},
            {"role": "user", "content": paper_text[:30000]}
        ],
        "max_tokens": 8000,
        "temperature": 0.1
    }
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
    }
    try:
        resp = requests.post(DEEPSEEK_API_URL, headers=headers, json=payload, timeout=120)
        if resp.status_code != 200:
            print(f"[parse] API HTTP {resp.status_code}: {resp.text[:200]}")
            return None
        result = resp.json()
        content = result["choices"][0]["message"]["content"]

        # Extract JSON from markdown code block
        m = re.search(r'```(?:json)?\s*([\s\S]*?)```', content)
        if m:
            content = m.group(1)
        else:
            m = re.search(r'\{[\s\S]*\}', content)
            if m:
                content = m.group()

        return json.loads(content)

    except json.JSONDecodeError as e:
        print(f"[parse] JSON parse error: {e}")
        if retry:
            print("[parse] Retrying with stricter prompt...")
            # Save partial content and try a fix-prompt
            fix_prompt = prompt + "\n\nIMPORTANT: You MUST output ONLY valid JSON. No trailing commas. No unescaped quotes. No markdown outside the JSON block. The JSON must be parseable by Python's json.loads()."
            return _call_deepseek(fix_prompt, paper_text[:20000], retry=False)
        return None
    except (KeyError, requests.RequestException) as e:
        print(f"[parse] API call failed: {e}")
        return None


def parse_paper(paper_id):
    """Parse a single paper: extract text, call AI, insert questions into DB.

    Returns number of questions extracted.
    """
    paper = get_paper(paper_id)
    if not paper:
        print(f"[parse] Paper {paper_id} not found")
        return 0

    # Get paper text
    paper_text = None
    if paper['file_path'] and os.path.exists(paper['file_path']):
        paper_text = _extract_text_from_pdf(paper['file_path'])

    if not paper_text:
        # Try to fetch from source URL as HTML
        try:
            import requests as r
            resp = r.get(paper['source_url'], headers={
                'User-Agent': 'Mozilla/5.0'
            }, timeout=30)
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(resp.text, 'lxml')
            paper_text = soup.get_text('\n', strip=True)
        except Exception as e:
            print(f"[parse] Cannot get text for {paper['title']}: {e}")
            return 0

    if not paper_text or len(paper_text) < 50:
        print(f"[parse] Paper text too short for {paper['title']}")
        return 0

    # Call AI
    result = _call_deepseek(EXTRACTION_PROMPT, paper_text)
    if not result or 'questions' not in result:
        print(f"[parse] AI extraction failed for {paper['title']}")
        return 0

    # Insert questions
    count = 0
    for q in result['questions']:
        options_json = json.dumps(q.get('options', []), ensure_ascii=False)
        insert_question(
            paper_id=paper_id,
            year=paper['year'],
            province=paper['province'],
            paper_type=paper['paper_type'],
            question_num=q.get('question_num', count + 1),
            q_type=q.get('q_type', '选择题'),
            stem=q.get('stem', ''),
            answer=q.get('answer', ''),
            options=options_json,
            explanation=q.get('explanation', ''),
            topics=q.get('topics', ''),
            source_url=paper['source_url']
        )
        count += 1

    print(f"[parse] {paper['title']}: extracted {count} questions")
    return count


def parse_all_papers():
    """Parse all papers in DB that have no questions yet."""
    conn = get_db()
    rows = conn.execute("""
        SELECT p.id FROM papers p
        WHERE NOT EXISTS (SELECT 1 FROM questions q WHERE q.paper_id = p.id)
        ORDER BY p.year DESC
    """).fetchall()
    conn.close()

    total = 0
    for (paper_id,) in rows:
        n = parse_paper(paper_id)
        total += n
    print(f"[parse] Total questions extracted: {total}")
    return total


def import_paper_from_text(year, province, paper_type, title, text, source_url=None):
    """Import a paper directly from text content (bypass PDF).

    Useful when the paper content is available as HTML/text directly.
    Creates the paper record and parses questions in one step.
    """
    from models import insert_paper
    paper_id = insert_paper(year, province, paper_type, title, source_url=source_url)
    result = _call_deepseek(EXTRACTION_PROMPT, text)
    if not result or 'questions' not in result:
        print(f"[parse] AI extraction failed for {title}")
        return 0

    count = 0
    for q in result['questions']:
        options_json = json.dumps(q.get('options', []), ensure_ascii=False)
        insert_question(
            paper_id=paper_id, year=year, province=province,
            paper_type=paper_type,
            question_num=q.get('question_num', count + 1),
            q_type=q.get('q_type', '选择题'),
            stem=q.get('stem', ''),
            answer=q.get('answer', ''),
            options=options_json,
            explanation=q.get('explanation', ''),
            topics=q.get('topics', ''),
            source_url=source_url
        )
        count += 1
    print(f"[parse] {title}: imported {count} questions")
    return count
