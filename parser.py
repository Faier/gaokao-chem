"""PDF text extraction and DeepSeek AI parsing for exam papers."""

import json
import re
import os
import requests

from config import DEEPSEEK_API_KEY, DEEPSEEK_API_URL, DEEPSEEK_MODEL

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


def extract_text_from_pdf(filepath):
    """Extract text from a PDF file. Tries pdfplumber first, then PyPDF2."""
    text_parts = []

    if HAS_PDFPLUMBER:
        try:
            with pdfplumber.open(filepath) as pdf:
                for page in pdf.pages:
                    t = page.extract_text()
                    if t:
                        text_parts.append(t)
            result = '\n\n'.join(text_parts)
            if result.strip():
                return result
        except Exception:
            pass

    if HAS_PYPDF2:
        try:
            with open(filepath, 'rb') as f:
                reader = PyPDF2.PdfReader(f)
                for page in reader.pages:
                    t = page.extract_text()
                    if t:
                        text_parts.append(t)
            result = '\n\n'.join(text_parts)
            if result.strip():
                return result
        except Exception:
            pass

    return None


def call_deepseek(paper_text, retry=True):
    """Send extraction request to DeepSeek API, return parsed JSON or None."""
    payload = {
        "model": DEEPSEEK_MODEL,
        "messages": [
            {"role": "system", "content": EXTRACTION_PROMPT},
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
        resp = requests.post(DEEPSEEK_API_URL, headers=headers, json=payload, timeout=180)
        if resp.status_code != 200:
            return {'error': f'API HTTP {resp.status_code}', 'raw': resp.text[:300]}
        result = resp.json()
        content = result["choices"][0]["message"]["content"]

        m = re.search(r'```(?:json)?\s*([\s\S]*?)```', content)
        if m:
            content = m.group(1)
        else:
            m = re.search(r'\{[\s\S]*\}', content)
            if m:
                content = m.group()

        return json.loads(content)

    except json.JSONDecodeError:
        if retry:
            return call_deepseek(paper_text[:20000], retry=False)
        return {'error': 'JSON parse failed'}
    except (KeyError, requests.RequestException) as e:
        return {'error': f'API call failed: {e}'}


def parse_pdf_to_questions(filepath):
    """Parse a PDF file into structured question data. Returns list of question dicts."""
    text = extract_text_from_pdf(filepath)
    if not text:
        return {'error': 'PDF 文字提取失败，文件可能为扫描件或加密'}
    if len(text) < 50:
        return {'error': 'PDF 文字内容过少'}

    result = call_deepseek(text)
    if not result:
        return {'error': 'AI 解析失败，请重试'}
    if 'error' in result:
        return result

    return {'questions': result.get('questions', []), 'raw_text': text[:5000]}
