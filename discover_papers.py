"""Discover gaokao chemistry paper URLs from 51jiaoxi.com search.

The site has a search endpoint that returns HTML with doc links.
We search for multiple keyword combinations to maximize coverage.
"""

import json
import re
import time
import requests
from bs4 import BeautifulSoup

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/125.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
}

BASE_URL = 'https://www.51jiaoxi.com'

SEARCH_QUERIES = [
    '高考化学真题 全国甲卷',
    '高考化学真题 全国乙卷',
    '高考化学真题 新课标',
    '高考化学真题 新高考',
    '北京高考化学真题',
    '上海高考化学真题',
    '天津高考化学真题',
    '浙江高考化学真题',
    '江苏高考化学真题',
    '广东高考化学真题',
    '山东高考化学真题',
    '高考理综化学真题',
]

PROVINCES = ['全国','北京','上海','天津','重庆','浙江','江苏','广东',
             '山东','湖北','湖南','河北','河南','四川','福建','安徽',
             '江西','山西','陕西','辽宁','吉林','黑龙江','云南','贵州',
             '广西','海南','甘肃','宁夏','青海','西藏','新疆','内蒙古']

PAPER_KEYWORDS = ['甲卷','乙卷','丙卷','新课标','新高考I','新高考II',
                  '新高考Ⅰ','新高考Ⅱ','理综','化学']


def parse_title(title):
    """Extract year, province, paper_type from title."""
    meta = {'province': '', 'paper_type': '', 'year': 0}

    # Year
    ym = re.search(r'(20\d{2})', title)
    if not ym:
        return None
    meta['year'] = int(ym.group(1))
    if meta['year'] < 2008 or meta['year'] > 2025:
        return None

    # Must be chemistry
    if '化学' not in title:
        return None

    # Province
    for p in PROVINCES:
        if p in title:
            meta['province'] = p
            break
    if not meta['province']:
        if '全国' in title or '新课标' in title or '新高考' in title:
            meta['province'] = '全国'
        else:
            meta['province'] = '全国'

    # Paper type
    for kw in PAPER_KEYWORDS:
        if kw in title:
            meta['paper_type'] = kw
            break

    meta['title'] = title.strip()
    return meta


def search_site(query):
    """Search 51jiaoxi.com and return list of paper metadata dicts."""
    results = []
    url = f'{BASE_URL}/search?keyword={query}'

    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        if resp.status_code != 200:
            print(f'  HTTP {resp.status_code}')
            return results

        soup = BeautifulSoup(resp.text, 'lxml')
        for a in soup.select('a[href*="/doc-"]'):
            href = a.get('href', '')
            title = a.get_text(strip=True)
            if not href or not title:
                continue

            meta = parse_title(title)
            if not meta:
                continue

            full_url = href if href.startswith('http') else BASE_URL + href
            meta['url'] = full_url
            meta['source'] = '51jiaoxi'
            results.append(meta)

    except Exception as e:
        print(f'  Error: {e}')

    return results


def main():
    all_papers = {}
    for query in SEARCH_QUERIES:
        print(f'Searching: {query}...')
        papers = search_site(query)
        print(f'  Found {len(papers)} papers')
        for p in papers:
            key = (p['year'], p['province'], p['paper_type'])
            if key not in all_papers:
                all_papers[key] = p
        time.sleep(1)  # Be polite

    # Sort and save
    papers_list = sorted(all_papers.values(), key=lambda x: (-x['year'], x['province']))
    print(f'\nTotal unique papers: {len(papers_list)}')

    for p in papers_list:
        print(f"  {p['year']} {p['province']} {p['paper_type']}: {p['title']}")

    with open('paper_urls.json', 'w', encoding='utf-8') as f:
        json.dump(papers_list, f, ensure_ascii=False, indent=2)
    print(f'\nSaved to paper_urls.json')


if __name__ == '__main__':
    main()
