"""Import a single PDF paper: extract text, AI parse, insert into DB.

Usage: python import_pdf.py <pdf_path> <year> <province> <paper_type> <title>
"""

import json
import sys
import os

from models import init_db, insert_paper, insert_question, paper_exists
from crawler.parse import _extract_text_from_pdf, _call_deepseek, EXTRACTION_PROMPT


def main():
    if len(sys.argv) < 6:
        print('Usage: python import_pdf.py <pdf_path> <year> <province> <paper_type> <title>')
        print('Example: python import_pdf.py data/papers/2025_四川_化学.pdf 2025 四川 化学 "2025年四川高考化学真题"')
        sys.exit(1)

    pdf_path = sys.argv[1]
    year = int(sys.argv[2])
    province = sys.argv[3]
    paper_type = sys.argv[4]
    title = sys.argv[5]

    init_db()

    # Check if already imported
    if paper_exists(year, province, paper_type):
        print(f'Paper already exists: {year} {province} {paper_type}')
        sys.exit(0)

    # Extract text
    print(f'Extracting text from: {pdf_path}')
    text = _extract_text_from_pdf(pdf_path)
    if not text:
        print('ERROR: Failed to extract text from PDF')
        sys.exit(1)

    cn = sum(1 for c in text if '一' <= c <= '鿿')
    print(f'Extracted {len(text)} chars, {cn} Chinese chars')

    if cn < 100:
        print('ERROR: Too little Chinese text extracted')
        sys.exit(1)

    # Show preview (safe encode)
    try:
        print('\n--- Text preview (first 300 chars) ---')
        print(text[:300])
        print('...\n')
    except UnicodeEncodeError:
        print('(preview skipped - encoding)\n')

    # AI parse
    print('Sending to DeepSeek for parsing...')
    result = _call_deepseek(EXTRACTION_PROMPT, text)
    if not result or 'questions' not in result:
        print('ERROR: AI parsing failed')
        sys.exit(1)

    # Insert
    paper_id = insert_paper(year, province, paper_type, title, file_path=pdf_path,
                           file_size=os.path.getsize(pdf_path))

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
        )
        count += 1

    print(f'\nDone! Imported {count} questions from: {title}')
    print(f'Paper ID: {paper_id}')


if __name__ == '__main__':
    main()
