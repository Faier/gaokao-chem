"""Download exam paper PDFs to local storage."""

import os
import requests

from config import PAPERS_DIR

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                  'AppleWebKit/537.36 (KHTML, like Gecko) '
                  'Chrome/125.0.0.0 Safari/537.36'
}
REQUEST_TIMEOUT = 60


def download_pdf(url, year, province, paper_type):
    """Download a PDF from url, save to data/papers/,
    return (file_path, file_size) or (None, None) on failure.

    Filename format: 2024_全国_甲卷.pdf
    """
    safe_province = province.replace('/', '_').replace('\\', '_')
    safe_type = paper_type.replace('/', '_').replace('\\', '_')
    filename = f"{year}_{safe_province}_{safe_type}.pdf"
    filepath = os.path.join(PAPERS_DIR, filename)

    if os.path.exists(filepath):
        size = os.path.getsize(filepath)
        return filepath, size

    try:
        resp = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT, stream=True)
        if resp.status_code != 200:
            print(f"[download] HTTP {resp.status_code} for {url}")
            return None, None

        content_type = resp.headers.get('Content-Type', '')
        if 'html' in content_type and 'pdf' not in content_type:
            print(f"[download] Not a PDF (Content-Type: {content_type}) for {url}")
            return None, None

        with open(filepath, 'wb') as f:
            for chunk in resp.iter_content(chunk_size=8192):
                f.write(chunk)

        size = os.path.getsize(filepath)
        if size < 10000:
            os.remove(filepath)
            print(f"[download] File too small ({size} bytes), likely not a valid PDF: {url}")
            return None, None

        print(f"[download] Saved {filename} ({size} bytes)")
        return filepath, size

    except Exception as e:
        print(f"[download] Failed: {url} - {e}")
        if os.path.exists(filepath):
            os.remove(filepath)
        return None, None


def download_all(missing_papers):
    """Given a list of paper metadata dicts (without file_path),
    download each and return the list with file_path populated.
    """
    results = []
    for p in missing_papers:
        url = p.get('pdf_url') or p.get('source_url')
        if not url:
            print(f"[download] No URL for {p['title']}")
            results.append(p)
            continue
        path, size = download_pdf(url, p['year'], p['province'], p['paper_type'])
        p['file_path'] = path
        p['file_size'] = size
        results.append(p)
    return results
