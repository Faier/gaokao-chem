"""Check content length for all discovered papers without parsing."""
import json
import re
import requests
from bs4 import BeautifulSoup

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/125.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
}

# Restore full list
import shutil
shutil.copy('paper_urls_full.json', 'paper_urls.json')

with open('paper_urls.json', 'r', encoding='utf-8') as f:
    papers = json.load(f)

good = []
thin = []
error = []

for i, p in enumerate(papers):
    label = f"{p['year']} {p['province']} {p['paper_type']}".strip()
    try:
        resp = requests.get(p['url'], headers=HEADERS, timeout=20)
        if resp.status_code != 200:
            error.append(p)
            print(f"[{i+1}/{len(papers)}] {label}: HTTP {resp.status_code}")
            continue

        if resp.apparent_encoding and 'gb' in resp.apparent_encoding.lower():
            resp.encoding = resp.apparent_encoding
        elif not resp.encoding or 'ISO' in resp.encoding:
            resp.encoding = 'utf-8'

        soup = BeautifulSoup(resp.text, 'lxml')
        for tag in soup(['script', 'style', 'nav', 'header', 'footer']):
            tag.decompose()
        text = soup.get_text('\n', strip=True)
        cn = len(re.findall(r'[一-鿿]', text))

        if cn >= 2000:
            good.append(p)
            print(f"[{i+1}/{len(papers)}] {label}: {cn} cn chars [GOOD]")
        else:
            thin.append(p)
            print(f"[{i+1}/{len(papers)}] {label}: {cn} cn chars [thin]")

    except Exception as e:
        error.append(p)
        print(f"[{i+1}/{len(papers)}] {label}: Error - {str(e)[:50]}")

print(f"\n{'='*50}")
print(f"Good (>=2000 cn chars): {len(good)}")
print(f"Thin (<2000 cn chars): {len(thin)}")
print(f"Errors: {len(error)}")

# Save good papers for batch processing
with open('paper_urls_good.json', 'w', encoding='utf-8') as f:
    json.dump(good, f, ensure_ascii=False, indent=2)
print("Saved good papers to paper_urls_good.json")
