"""Batch fetch and parse all discovered papers from paper_urls.json.

Usage: python batch_fetch.py
"""

import json
import re
import time
import requests
from bs4 import BeautifulSoup

from models import init_db, insert_paper, insert_question, paper_exists, get_stats
from crawler.parse import _call_deepseek, EXTRACTION_PROMPT

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/125.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
}


def fetch_page_text(url):
    """Fetch a page and extract meaningful text."""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=30)
    except requests.exceptions.SSLError as e:
        print(f'  SSL Error: {e}')
        return None
    except requests.exceptions.ConnectionError as e:
        print(f'  Connection Error: {e}')
        return None
    if resp.status_code != 200:
        return None

    if resp.apparent_encoding and 'gb' in resp.apparent_encoding.lower():
        resp.encoding = resp.apparent_encoding
    elif not resp.encoding or 'ISO' in resp.encoding:
        resp.encoding = 'utf-8'

    soup = BeautifulSoup(resp.text, 'lxml')
    for tag in soup(['script', 'style', 'nav', 'header', 'footer']):
        tag.decompose()

    text = soup.get_text('\n', strip=True)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text


def parse_and_store(year, province, paper_type, title, text, source_url):
    """Parse paper text with AI and store in DB."""
    cn_chars = len(re.findall(r'[一-鿿]', text))
    print(f'  Text: {len(text)} chars, {cn_chars} Chinese chars')

    if cn_chars < 200:
        print(f'  Too little Chinese content, skipping')
        return 0

    result = _call_deepseek(EXTRACTION_PROMPT, text)
    if not result or 'questions' not in result:
        print(f'  AI parsing failed')
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

    print(f'  Parsed {count} questions')
    return count


def main():
    init_db()

    with open('paper_urls.json', 'r', encoding='utf-8') as f:
        papers = json.load(f)

    total_q = 0
    success = 0
    skipped = 0
    failed = 0

    for i, p in enumerate(papers):
        label = f"{p['year']} {p['province']} {p['paper_type']}".strip()
        print(f"\n[{i+1}/{len(papers)}] {label}: {p['title'][:60]}")

        # Skip if already in DB
        if paper_exists(p['year'], p['province'], p['paper_type']):
            print(f'  Already in DB, skipping')
            skipped += 1
            continue

        # Fetch
        text = fetch_page_text(p['url'])
        if not text:
            print(f'  Failed to fetch')
            failed += 1
            continue

        # Parse
        n = parse_and_store(p['year'], p['province'], p['paper_type'],
                           p['title'], text, p['url'])
        if n > 0:
            success += 1
            total_q += n
        else:
            failed += 1

        # Rate limit: wait between API calls
        time.sleep(3)

    print(f"\n{'='*50}")
    print(f"Done! Success: {success}, Skipped: {skipped}, Failed: {failed}")
    print(f"New questions: {total_q}")
    stats = get_stats()
    print(f"DB totals: {stats}")


if __name__ == '__main__':
    main()
