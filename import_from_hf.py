"""Import gaokao chemistry questions from HuggingFace datasets into our DB.

Sources:
  - AGIEval: hails/agieval-gaokao-chemistry (207 MCQs)
  - Gaokao-Bench: RUCAIBox/gaokao-bench 2010-2022_Chemistry_MCQs (124 MCQs)

Run with: HF_ENDPOINT=https://hf-mirror.com python import_from_hf.py
"""

import json
import os
import re

os.environ.setdefault('HF_ENDPOINT', 'https://hf-mirror.com')
os.environ.setdefault('HF_HUB_DISABLE_SYMLINKS_WARNING', '1')

from datasets import load_dataset
from models import init_db, insert_paper, insert_question, get_stats


def import_agieval():
    """Import AGIEval gaokao-chemistry dataset."""
    ds = load_dataset("hails/agieval-gaokao-chemistry", split="test")
    print(f"[AGIEval] Loading {len(ds)} questions...")

    paper_id = insert_paper(
        year=2023,
        province='全国',
        paper_type='AGIEval合集',
        title='AGIEval 高考化学选择题合集',
        source_url='https://huggingface.co/datasets/hails/agieval-gaokao-chemistry'
    )

    count = 0
    for i, item in enumerate(ds, 1):
        query = item['query']
        choices = item['choices']
        gold_val = item['gold']
        gold_idx = gold_val[0] if isinstance(gold_val, list) else gold_val

        # Parse query to extract stem (everything before choices)
        stem = query
        # Try to separate: query often contains "选项：(A)..." at the end
        m = re.search(r'选项[：:](.*)$', query)
        if m:
            stem = query[:m.start()].strip()

        # Map gold index to letter
        letters = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H']
        answer = letters[gold_idx] if gold_idx < len(letters) else str(gold_idx)

        # Build options JSON
        options = []
        for j, choice_text in enumerate(choices):
            letter = letters[j] if j < len(letters) else str(j)
            options.append({letter: choice_text})

        insert_question(
            paper_id=paper_id, year=2023, province='全国', paper_type='AGIEval合集',
            question_num=i, q_type='选择题', stem=stem,
            answer=answer, options=json.dumps(options, ensure_ascii=False),
            source_url='https://huggingface.co/datasets/hails/agieval-gaokao-chemistry'
        )
        count += 1

    print(f"[AGIEval] Imported {count} questions")
    return count


def parse_gaokao_bench_category(category):
    """Parse category string like '全国甲卷' or '新课标Ⅰ卷' into province + paper_type."""
    province_map = {
        '全国': '全国', '新课标': '全国', '北京': '北京', '上海': '上海',
        '天津': '天津', '浙江': '浙江', '江苏': '江苏',
    }
    province = '全国'
    paper_type = category
    for key, val in province_map.items():
        if key in category:
            province = val
            paper_type = category
            break
    return province, paper_type


def import_gaokao_bench():
    """Import Gaokao-Bench 2010-2022 Chemistry MCQs."""
    ds = load_dataset("RUCAIBox/gaokao-bench", "2010-2022_Chemistry_MCQs", split="test")
    print(f"[Gaokao-Bench] Loading {len(ds)} questions...")

    # Group by (year, category) to create papers
    papers = {}
    for item in ds:
        year = str(item['year'])
        category = str(item['category'])
        key = (year, category)
        if key not in papers:
            papers[key] = []
        papers[key].append(item)

    total = 0
    for (year, category), items in papers.items():
        province, paper_type = parse_gaokao_bench_category(category)
        title = f"{year}年高考化学{category}"

        paper_id = insert_paper(
            year=int(year), province=province, paper_type=paper_type,
            title=title,
            source_url='https://huggingface.co/datasets/RUCAIBox/gaokao-bench'
        )

        for item in items:
            stem = item['question']
            answer = item['answer'][0] if item['answer'] else ''
            explanation = item.get('analysis', '') or ''
            score = item.get('score', '')

            # Parse options from stem if they're embedded (LaTeX format: A. ... B. ...)
            options = []
            opt_pattern = r'([A-D])\.\s*(.+?)(?=\s*[A-D]\.\s|\s*$|$)'
            opt_matches = re.findall(opt_pattern, stem, re.DOTALL)
            if opt_matches:
                options = [{letter: text.strip()} for letter, text in opt_matches]
                # Remove options part from stem
                first_opt = re.search(r'\s[A-D]\.\s', stem)
                if first_opt:
                    stem = stem[:first_opt.start()].strip()

            insert_question(
                paper_id=paper_id, year=int(year), province=province,
                paper_type=paper_type,
                question_num=item.get('index', 0) + 1,
                q_type='选择题', stem=stem,
                answer=answer,
                options=json.dumps(options, ensure_ascii=False),
                explanation=explanation,
                source_url='https://huggingface.co/datasets/RUCAIBox/gaokao-bench'
            )
            total += 1

    print(f"[Gaokao-Bench] Imported {total} questions into {len(papers)} papers")
    return total


def main():
    init_db()

    # Check existing data
    stats = get_stats()
    if stats['total_questions'] > 10:
        print(f"Database already has {stats['total_questions']} questions. Skipping import.")
        print("Delete data/chem.db to re-import from scratch.")
        return

    n1 = import_gaokao_bench()
    n2 = import_agieval()

    print(f"\n{'='*50}")
    print(f"Total imported: {n1 + n2} questions")
    stats = get_stats()
    print(f"DB stats: {stats}")


if __name__ == '__main__':
    main()
