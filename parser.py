"""Document extraction and Mimo AI parsing for exam papers."""

import base64
import json
import os
import re
import tempfile

import requests

from config import MIMO_API_KEY, MIMO_API_URL, MIMO_MODEL

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

try:
    import fitz
    HAS_FITZ = True
except ImportError:
    HAS_FITZ = False

try:
    from docx import Document
    HAS_DOCX = True
except ImportError:
    HAS_DOCX = False


EXTRACTION_PROMPT = """你是一个高考化学试卷解析专家。请将下面的试卷内容解析为结构化题目列表。
一份标准的高考化学试卷通常包含 10-15 道题目。请只提取真正的考试题目，不要提取试卷说明、答题须知、评分标准、目录、页眉页脚等非题目内容。

对于每道题目，提取以下字段并以 JSON 数组格式返回：
- question_num: 题号，整数
- q_type: 题型，只能是 "选择题" / "填空题" / "实验题" / "计算题" / "简答题" 之一
- stem: 题干原文，完整保留，包括化学方程式、图表说明和符号；大题下所有小问合并到同一个 stem
- options: 选项列表，如 [{"A":"..."},{"B":"..."}]；非选择题为空数组
- answer: 标准答案。文档中已有答案或解析时，必须以文档原文为准；只有文档没有明确答案时，才根据题目内容推断最合理答案
- explanation: 解题分析。文档中已有答案或解析时，必须以文档原文为准，不要改写、替换或重新推断；只有文档没有解析时，才生成包括考查知识点、解题思路、关键步骤和易错点的解析，不少于 50 字
- topics: 涉及的知识点关键词，用空格分隔，至少 2 个

重要规则：
1. 每道题必须有 answer 和 explanation，不能留空。
2. 选择题的 answer 必须是单个选项字母。
3. 每道大题作为一个整体，不要拆成多个小题。
4. 如果 PDF 文字乱码、公式显示不正常，结合页面图片和上下文还原。
5. 如果文档后半部分、答案页、解析页、表格或图片中包含“参考答案”“答案”“解析”“详解”等内容，先匹配到对应题号，再填入 answer 和 explanation；不得用你自己的答案覆盖文档已有内容。

只返回下面格式的 JSON，不要包含其他内容：
{
  "questions": [
    {
      "question_num": 1,
      "q_type": "选择题",
      "stem": "...",
      "options": [{"A":"..."},{"B":"..."}],
      "answer": "B",
      "explanation": "本题考查...",
      "topics": "关键字 关键字"
    }
  ]
}
"""


def get_document_kind(filepath):
    """Return supported document kind for a path, or None if unsupported."""
    ext = os.path.splitext(filepath)[1].lower()
    if ext == ".pdf":
        return "pdf"
    if ext in {".doc", ".docx"}:
        return "word"
    return None


def extract_text_from_pdf(filepath):
    """Extract text from a PDF file and keep the richest chemistry text."""
    candidates = []

    if HAS_PDFPLUMBER:
        try:
            with pdfplumber.open(filepath) as pdf:
                text_parts = []
                layout_parts = []
                for page in pdf.pages:
                    text = page.extract_text()
                    if text:
                        text_parts.append(text)
                    layout_text = page.extract_text(layout=True, x_tolerance=1, y_tolerance=3)
                    if layout_text:
                        layout_parts.append(layout_text)
                candidates.append("\n\n".join(text_parts))
                candidates.append("\n\n".join(layout_parts))
        except Exception:
            pass

    if HAS_PYPDF2:
        try:
            text_parts = []
            with open(filepath, "rb") as f:
                reader = PyPDF2.PdfReader(f)
                for page in reader.pages:
                    text = page.extract_text()
                    if text:
                        text_parts.append(text)
            candidates.append("\n\n".join(text_parts))
        except Exception:
            pass

    if HAS_FITZ:
        try:
            doc = fitz.open(filepath)
            try:
                text_parts = []
                block_parts = []
                for page in doc:
                    text = page.get_text("text")
                    if text:
                        text_parts.append(text)
                    blocks = page.get_text("blocks")
                    if blocks:
                        blocks = sorted(blocks, key=lambda b: (round(b[1]), b[0]))
                        block_parts.extend(b[4] for b in blocks if len(b) > 4 and b[4].strip())
                candidates.append("\n\n".join(text_parts))
                candidates.append("\n".join(block_parts))
            finally:
                doc.close()
        except Exception:
            pass

    return choose_best_pdf_text(candidates)


def choose_best_pdf_text(candidates):
    """Choose the extracted PDF text that best preserves chemistry questions."""
    clean_candidates = [c for c in candidates if c and c.strip()]
    if not clean_candidates:
        return None
    return max(clean_candidates, key=_score_pdf_text)


def _score_pdf_text(text):
    compact = re.sub(r"\s+", "", text)
    score = len(text) * 0.01
    score += len(re.findall(r"[A-D][\.．、]", text)) * 30
    score += len(re.findall(r"[①②③④⑤⑥⑦⑧⑨⑩]", text)) * 20
    score += len(re.findall(r"ΔH|kJ/mol|mol|aq|g\)|l\)|s\)", text)) * 18
    score += len(re.findall(r"[A-Z][a-z]?\d*", compact)) * 3
    score += len(re.findall(r"[+=→⇌]", text)) * 5
    score += len(re.findall(r"N2H4|NH3|H2O|CO2|H2SO4|NaOH", compact)) * 25
    return score


def render_pdf_pages_as_data_urls(filepath, max_pages=8, zoom=1.8):
    """Render PDF pages to PNG data URLs for multimodal model parsing."""
    if not HAS_FITZ:
        return []

    images = []
    try:
        doc = fitz.open(filepath)
        try:
            for page in doc[:max_pages]:
                pixmap = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False)
                encoded = base64.b64encode(pixmap.tobytes("png")).decode("ascii")
                images.append(f"data:image/png;base64,{encoded}")
        finally:
            doc.close()
    except Exception:
        return []
    return images


def extract_pdf_embedded_images_as_data_urls(filepath, max_images=24):
    """Extract images embedded inside a PDF as data URLs."""
    if not HAS_FITZ:
        return []

    images = []
    seen = set()
    try:
        doc = fitz.open(filepath)
        try:
            for page_index in range(len(doc)):
                for image_info in doc.get_page_images(page_index, full=True):
                    xref = image_info[0]
                    if xref in seen:
                        continue
                    seen.add(xref)
                    image = doc.extract_image(xref)
                    image_bytes = image.get("image")
                    ext = image.get("ext", "png").lower()
                    if not image_bytes:
                        continue
                    if ext in {"jpg", "jpeg"}:
                        mime = "image/jpeg"
                    elif ext == "webp":
                        mime = "image/webp"
                    else:
                        mime = "image/png"
                    encoded = base64.b64encode(image_bytes).decode("ascii")
                    images.append(f"data:{mime};base64,{encoded}")
                    if len(images) >= max_images:
                        return images
        finally:
            doc.close()
    except Exception:
        return []
    return images


def extract_text_from_word(filepath):
    """Extract text from docx files, with a best-effort Windows fallback for doc."""
    ext = os.path.splitext(filepath)[1].lower()
    if ext == ".docx":
        if not HAS_DOCX:
            return None
        try:
            doc = Document(filepath)
            parts = [p.text for p in doc.paragraphs if p.text.strip()]
            for table in doc.tables:
                for row in table.rows:
                    cells = [cell.text.strip() for cell in row.cells if cell.text.strip()]
                    if cells:
                        parts.append("\t".join(cells))
            return "\n".join(parts) or None
        except Exception:
            return None

    if ext == ".doc":
        return _extract_text_from_legacy_doc(filepath)

    return None


def _extract_text_from_legacy_doc(filepath):
    """Use Microsoft Word COM automation when available to read legacy .doc."""
    try:
        import win32com.client
    except ImportError:
        return None

    word = None
    temp_path = None
    try:
        word = win32com.client.DispatchEx("Word.Application")
        word.Visible = False
        doc = word.Documents.Open(os.path.abspath(filepath), ReadOnly=True)
        fd, temp_path = tempfile.mkstemp(suffix=".txt")
        os.close(fd)
        doc.SaveAs(temp_path, FileFormat=2)
        doc.Close(False)
        with open(temp_path, "r", encoding="utf-8", errors="ignore") as f:
            return f.read().strip() or None
    except Exception:
        return None
    finally:
        if word is not None:
            try:
                word.Quit()
            except Exception:
                pass
        if temp_path and os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except OSError:
                pass


def extract_text_from_document(filepath):
    """Extract text from a supported document path."""
    kind = get_document_kind(filepath)
    if kind == "pdf":
        return extract_text_from_pdf(filepath)
    if kind == "word":
        return extract_text_from_word(filepath)
    return None


def call_mimo(paper_text, image_urls=None, system_prompt=EXTRACTION_PROMPT, retry=True):
    """Send extraction request to the Mimo OpenAI-compatible API."""
    if not MIMO_API_KEY:
        return {"error": "缺少 MIMO_API_KEY 环境变量，无法调用 Mimo 模型"}

    user_content = paper_text[:40000]
    if image_urls:
        user_content = [{"type": "text", "text": paper_text[:20000]}]
        user_content.extend(
            {"type": "image_url", "image_url": {"url": image_url}}
            for image_url in image_urls
        )

    payload = {
        "model": MIMO_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ],
        "max_tokens": 16000,
        "temperature": 0.1,
    }
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {MIMO_API_KEY}",
    }
    try:
        resp = requests.post(MIMO_API_URL, headers=headers, json=payload, timeout=180)
        if resp.status_code != 200:
            return {"error": f"API HTTP {resp.status_code}", "raw": resp.text[:300]}
        result = resp.json()
        content = result["choices"][0]["message"]["content"]
        return _parse_json_content(content)
    except json.JSONDecodeError:
        if retry:
            return call_mimo(paper_text[:20000], image_urls=None, system_prompt=system_prompt, retry=False)
        return {"error": "JSON parse failed"}
    except (KeyError, requests.RequestException) as e:
        return {"error": f"API call failed: {e}"}


def _parse_json_content(content):
    m = re.search(r"```(?:json)?\s*([\s\S]*?)```", content)
    if m:
        content = m.group(1)
    else:
        m = re.search(r"\{[\s\S]*\}", content)
        if m:
            content = m.group()
    return json.loads(content)


def call_deepseek(paper_text, retry=True):
    """Compatibility wrapper for older imports."""
    return call_mimo(paper_text, retry=retry)


def parse_document_to_questions(filepath):
    """Parse a PDF, DOC, or DOCX file into structured question data."""
    kind = get_document_kind(filepath)
    if not kind:
        return {"error": "仅支持 PDF、DOC、DOCX 文档"}

    text = extract_text_from_document(filepath) or ""
    image_urls = []
    used_embedded_images = False

    if kind == "pdf":
        image_urls = extract_pdf_embedded_images_as_data_urls(filepath)
        used_embedded_images = bool(image_urls)
        if not text.strip() and not image_urls:
            image_urls = render_pdf_pages_as_data_urls(filepath)

    if not text.strip() and not image_urls:
        return {"error": "文档文字提取失败，文件可能为扫描件、加密文件或旧版 Word 文档缺少转换组件"}

    if len(text.strip()) < 50 and not image_urls:
        return {"error": "文档文字内容过少"}

    prompt_text = text
    if image_urls:
        image_note = "PDF embedded images" if used_embedded_images else "PDF page images"
        prompt_text = (
            f"{text}\n\n{image_note} are attached. "
            "Use them to recover diagrams, equations, tables, and visual question content."
        )

    result = call_mimo(prompt_text, image_urls=image_urls or None)
    if not result:
        return {"error": "AI 解析失败，请重试"}
    if "error" in result:
        return result

    return {"questions": result.get("questions", []), "raw_text": text[:5000]}


def parse_pdf_to_questions(filepath):
    """Compatibility wrapper for older PDF-only callers."""
    return parse_document_to_questions(filepath)
