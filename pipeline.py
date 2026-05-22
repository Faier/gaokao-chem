"""Run the full data pipeline: discover → download → parse.

Usage: python pipeline.py
"""

from models import init_db, paper_exists, insert_paper
from crawler.discover import discover
from crawler.download import download_pdf
from crawler.parse import parse_paper


def run_pipeline():
    init_db()

    print("=" * 50)
    print("Step 1: Discovering papers...")
    papers = discover()

    if not papers:
        print("No papers discovered. Check network or site availability.")
        return

    print(f"\nStep 2: Registering {len(papers)} papers and downloading PDFs...")
    for i, p in enumerate(papers, 1):
        print(f"\n[{i}/{len(papers)}] {p['title']}")

        # Skip if already in DB
        if paper_exists(p['year'], p['province'], p['paper_type']):
            print(f"  Already in database, skipping")
            continue

        # Insert paper record
        paper_id = insert_paper(
            year=p['year'],
            province=p['province'],
            paper_type=p['paper_type'],
            title=p['title'],
            source_url=p.get('source_url', '')
        )

        # Try to download PDF
        url = p.get('pdf_url') or p.get('source_url')
        if url:
            path, size = download_pdf(url, p['year'], p['province'], p['paper_type'])
            if path:
                from models import update_paper_file
                update_paper_file(paper_id, path, size)
                print(f"  Downloaded: {path}")

    print(f"\nStep 3: Parsing papers and extracting questions...")
    from crawler.parse import parse_all_papers
    total = parse_all_papers()
    print(f"\nDone! {total} questions extracted from {len(papers)} papers.")


if __name__ == '__main__':
    run_pipeline()
