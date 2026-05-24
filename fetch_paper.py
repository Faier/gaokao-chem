"""Fetch and parse a single gaokao chemistry paper from a known source URL.

Usage: python fetch_paper.py
"""

import re
import json
import requests
from bs4 import BeautifulSoup

from models import init_db, insert_paper, insert_question, paper_exists
from crawler.parse import _call_deepseek, EXTRACTION_PROMPT

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/125.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
}


def fetch_page_text(url):
    """Fetch a page and extract meaningful text content."""
    resp = requests.get(url, headers=HEADERS, timeout=30)
    if resp.status_code != 200:
        print(f"HTTP {resp.status_code}")
        return None

    # Handle encoding
    if resp.apparent_encoding and 'gb' in resp.apparent_encoding.lower():
        resp.encoding = resp.apparent_encoding
    elif not resp.encoding or 'ISO' in resp.encoding:
        resp.encoding = 'utf-8'

    soup = BeautifulSoup(resp.text, 'lxml')

    # Remove script, style, nav elements
    for tag in soup(['script', 'style', 'nav', 'header', 'footer']):
        tag.decompose()

    text = soup.get_text('\n', strip=True)
    # Collapse multiple newlines
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text


def parse_and_store(year, province, paper_type, title, text, source_url):
    """Parse paper text with AI and store questions in DB."""
    print(f"  Sending {len(text)} chars to DeepSeek for parsing...")

    result = _call_deepseek(EXTRACTION_PROMPT, text)
    if not result or 'questions' not in result:
        print(f"  AI parsing failed")
        return 0

    paper_id = insert_paper(year, province, paper_type, title, source_url=source_url)

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

    print(f"  Parsed {count} questions")
    return count


def main():
    init_db()

    # Test with 2024 全国甲卷 from 51jiaoxi
    test_papers = [
        {
            'year': 2024,
            'province': '全国',
            'paper_type': '甲卷',
            'title': '2024年高考化学全国甲卷',
            'url': 'https://www.51jiaoxi.com/doc-15876559.html',
        },
        {
            'year': 2024,
            'province': '全国',
            'paper_type': '新课标卷',
            'title': '2024年高考化学新课标卷',
            'url': 'https://www.51jiaoxi.com/doc-15881637.html',
        },
    ]

    for p in test_papers:
        if paper_exists(p['year'], p['province'], p['paper_type']):
            print(f"Already exists: {p['title']}, skipping")
            continue

        print(f"Fetching: {p['title']}")
        text = fetch_page_text(p['url'])
        if not text:
            print(f"  Failed to fetch")
            continue

        cn_chars = len(re.findall(r'[一-鿿]', text))
        print(f"  Got {cn_chars} Chinese chars")

        if cn_chars < 500:
            print(f"  Too little content, skipping")
            continue

        n = parse_and_store(p['year'], p['province'], p['paper_type'],
                           p['title'], text, p['url'])
        print(f"  Total: {n} questions\n")


if __name__ == '__main__':
    main()
