"""Discover Gaokao chemistry exam papers from public education websites.

Each source function yields paper metadata dicts:
  {year, province, paper_type, title, source_url, [pdf_url]}

The main discover() function aggregates results from all sources and
deduplicates by (year, province, paper_type).
"""

import requests
from bs4 import BeautifulSoup

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                  'AppleWebKit/537.36 (KHTML, like Gecko) '
                  'Chrome/125.0.0.0 Safari/537.36'
}
REQUEST_TIMEOUT = 30


def _fetch_page(url):
    resp = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
    resp.encoding = resp.apparent_encoding or 'utf-8'
    return resp.text


def _source_gaokao_com():
    """Scrape gaokao.com for chemistry exam paper listings.

    Crawls the chemistry subject listing pages. Each page contains
    links to individual exam papers with year/province metadata.
    """
    results = []
    base_url = 'https://www.gaokao.com/gaokao/lnzt/hx/'
    try:
        html = _fetch_page(base_url)
        soup = BeautifulSoup(html, 'lxml')
        for item in soup.select('a[href*="hx"]'):
            href = item.get('href', '')
            title = item.get_text(strip=True)
            if not href or not title:
                continue
            if not href.startswith('http'):
                href = 'https://www.gaokao.com' + href
            meta = _parse_title_meta(title)
            if meta:
                meta['source_url'] = href
                results.append(meta)
    except Exception as e:
        print(f"[gaokao.com] fetch failed: {e}")
    return results


def _source_zujuan_xkw():
    """Scrape zujuan.xkw.com (组卷网) for chemistry exam papers.

    This site has structured listings by year and province.
    """
    results = []
    base_url = 'https://zujuan.xkw.com/gaokao/hx/'
    try:
        html = _fetch_page(base_url)
        soup = BeautifulSoup(html, 'lxml')
        for item in soup.select('a[href*="/paper/"]'):
            href = item.get('href', '')
            title = item.get_text(strip=True)
            if not href or not title:
                continue
            if not href.startswith('http'):
                href = 'https://zujuan.xkw.com' + href
            meta = _parse_title_meta(title)
            if meta:
                meta['source_url'] = href
                results.append(meta)
    except Exception as e:
        print(f"[zujuan.xkw.com] fetch failed: {e}")
    return results


def _source_eol_cn():
    """Scrape gaokao.eol.cn for exam papers and answers.

    中国教育在线 has free gaokao papers organized by year/subject.
    """
    results = []
    base_urls = [
        f'https://gaokao.eol.cn/huaxue/',
    ]
    for base_url in base_urls:
        try:
            html = _fetch_page(base_url)
            soup = BeautifulSoup(html, 'lxml')
            for item in soup.select('a[href*="huaxue"]'):
                href = item.get('href', '')
                title = item.get_text(strip=True)
                if not href or not title:
                    continue
                if not href.startswith('http'):
                    href = 'https://gaokao.eol.cn' + href
                meta = _parse_title_meta(title)
                if meta:
                    meta['source_url'] = href
                    results.append(meta)
        except Exception as e:
            print(f"[eol.cn] fetch failed: {e}")
    return results


PROVINCES = ['全国', '北京', '上海', '天津', '重庆', '浙江', '江苏', '广东',
             '山东', '湖北', '湖南', '河北', '河南', '四川', '福建', '安徽',
             '江西', '山西', '陕西', '辽宁', '吉林', '黑龙江', '云南', '贵州',
             '广西', '海南', '甘肃', '宁夏', '青海', '西藏', '新疆', '内蒙古']

PAPER_TYPE_KEYWORDS = ['甲卷', '乙卷', '丙卷', '新课标', '新高考I', '新高考II',
                       '新高考Ⅰ', '新高考Ⅱ', '理综', '化学']


def _parse_title_meta(title):
    """Extract year, province, paper_type from a paper title string.

    Examples:
      "2024年高考化学全国甲卷" → {year:2024, province:"全国", paper_type:"甲卷"}
      "2023北京高考化学试卷" → {year:2023, province:"北京", paper_type:"化学"}
    """
    import re

    meta = {'province': '', 'paper_type': ''}

    # Extract year
    year_match = re.search(r'(20\d{2})', title)
    if not year_match:
        return None
    meta['year'] = int(year_match.group(1))
    if meta['year'] < 2008 or meta['year'] > 2026:
        return None

    # Only chemistry
    if '化学' not in title:
        return None

    # Extract province
    for p in PROVINCES:
        if p in title:
            meta['province'] = p
            break
    if not meta['province']:
        meta['province'] = '全国'

    # Extract paper type
    for kw in PAPER_TYPE_KEYWORDS:
        if kw in title:
            meta['paper_type'] = kw
            break
    if not meta['paper_type']:
        meta['paper_type'] = ''

    meta['title'] = title.strip()
    return meta


def discover():
    """Run all sources and return deduplicated paper metadata list.

    Deduplicates by (year, province, paper_type).
    """
    all_results = []
    for source_fn in [_source_gaokao_com, _source_zujuan_xkw, _source_eol_cn]:
        try:
            results = source_fn()
            all_results.extend(results)
            print(f"[discover] {source_fn.__name__}: found {len(results)} papers")
        except Exception as e:
            print(f"[discover] {source_fn.__name__}: error {e}")

    # Deduplicate
    seen = set()
    unique = []
    for r in all_results:
        key = (r['year'], r['province'], r['paper_type'])
        if key not in seen:
            seen.add(key)
            unique.append(r)

    unique.sort(key=lambda x: (x['year'], x['province']))
    print(f"[discover] total unique papers: {len(unique)}")
    return unique


if __name__ == '__main__':
    papers = discover()
    for p in papers:
        print(f"  {p['year']} {p['province']} {p['paper_type']}: {p['title']}")
