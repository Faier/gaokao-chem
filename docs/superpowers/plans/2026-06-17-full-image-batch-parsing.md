# Full Image Batch Parsing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Parse imported exam papers without dropping images, even when a DOCX/PDF contains more images than a safe single API request can handle.

**Architecture:** Image extraction stays responsible for extracting every embedded image in stable document order and compressing each image. API batching moves into parsing orchestration: `parse_document_to_questions()` sends all images in chunks, merges question records by `question_num`, and preserves text-only parsing behavior for documents without images.

**Tech Stack:** Python 3.12, Flask app code, OpenAI-compatible multimodal chat API, pytest/unittest, Pillow for image compression, python-docx/PyMuPDF existing document extraction libraries.

---

## File Structure

- Modify `parser.py`
  - Keep `_natural_sort_key()` and `_compress_image_to_jpeg_bytes()` as low-level helpers.
  - Change PDF/DOCX image extraction defaults so they do not truncate by default.
  - Add `chunk_items(items, chunk_size)` for deterministic batching.
  - Add `merge_question_batches(batch_results)` for deduplicating model outputs by `question_num`.
  - Add `call_mimo_with_image_batches(paper_text, image_urls, batch_size=12)` for multi-call parsing.
  - Update `parse_document_to_questions()` to use batching when `image_urls` exist.
- Modify `tests/test_parser_documents.py`
  - Add tests that extraction does not truncate >24 DOCX images.
  - Add tests that batching splits image lists and calls `call_mimo()` once per chunk.
  - Add tests that batch merge deduplicates questions by number, preferring later image-aware results.

---

### Task 1: Make Image Extraction Unlimited by Default

**Files:**
- Modify: `parser.py:225-314`
- Test: `tests/test_parser_documents.py`

- [ ] **Step 1: Write failing DOCX extraction test**

Add this test method to `DocumentParserTests` in `tests/test_parser_documents.py`:

```python
    def test_extract_docx_embedded_images_does_not_truncate_by_default(self):
        import io
        import zipfile

        try:
            from PIL import Image
        except ImportError:
            self.skipTest("Pillow is not installed")

        def png_bytes(i):
            buf = io.BytesIO()
            Image.new("RGB", (20, 20), (i % 255, 0, 0)).save(buf, format="PNG")
            return buf.getvalue()

        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "many-images.docx")
            with zipfile.ZipFile(path, "w") as zf:
                zf.writestr("word/document.xml", "<doc/>")
                for i in range(1, 31):
                    zf.writestr(f"word/media/image{i}.png", png_bytes(i))

            urls = parser.extract_docx_embedded_images_as_data_urls(path)

        self.assertEqual(len(urls), 30)
        self.assertTrue(all(u.startswith("data:image/jpeg;base64,") for u in urls))
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
cd D:/Claude/gaokao-chem && python -m pytest tests/test_parser_documents.py::DocumentParserTests::test_extract_docx_embedded_images_does_not_truncate_by_default -v
```

Expected: FAIL with `AssertionError: 24 != 30` if extraction still truncates at 24.

- [ ] **Step 3: Update image extraction signatures**

In `parser.py`, change both extraction signatures:

```python
def extract_pdf_embedded_images_as_data_urls(filepath, max_images=None):
```

```python
def extract_docx_embedded_images_as_data_urls(filepath, max_images=None):
```

In both functions, keep the existing loop but change the break condition from:

```python
                    if len(images) >= max_images:
                        return images
```

or:

```python
                if len(images) >= max_images:
                    break
```

to:

```python
                    if max_images is not None and len(images) >= max_images:
                        return images
```

and:

```python
                if max_images is not None and len(images) >= max_images:
                    break
```

- [ ] **Step 4: Run focused test to verify pass**

Run:

```bash
cd D:/Claude/gaokao-chem && python -m pytest tests/test_parser_documents.py::DocumentParserTests::test_extract_docx_embedded_images_does_not_truncate_by_default -v
```

Expected: PASS.

---

### Task 2: Add Batch Helpers

**Files:**
- Modify: `parser.py` near `_parse_json_content()`
- Test: `tests/test_parser_documents.py`

- [ ] **Step 1: Write failing helper tests**

Add these tests to `DocumentParserTests`:

```python
    def test_chunk_items_splits_without_dropping_items(self):
        chunks = parser.chunk_items(list(range(25)), 12)
        self.assertEqual(chunks, [list(range(12)), list(range(12, 24)), [24]])

    def test_merge_question_batches_prefers_later_duplicate_question_numbers(self):
        batches = [
            {"questions": [
                {"question_num": 1, "stem": "text only", "answer": "A"},
                {"question_num": 2, "stem": "text q2", "answer": "B"},
            ]},
            {"questions": [
                {"question_num": 2, "stem": "image-aware q2", "answer": "C"},
                {"question_num": 3, "stem": "image-aware q3", "answer": "D"},
            ]},
        ]

        merged = parser.merge_question_batches(batches)

        self.assertEqual([q["question_num"] for q in merged["questions"]], [1, 2, 3])
        self.assertEqual(merged["questions"][1]["stem"], "image-aware q2")
        self.assertEqual(merged["questions"][1]["answer"], "C")
```

- [ ] **Step 2: Run helper tests to verify they fail**

Run:

```bash
cd D:/Claude/gaokao-chem && python -m pytest tests/test_parser_documents.py::DocumentParserTests::test_chunk_items_splits_without_dropping_items tests/test_parser_documents.py::DocumentParserTests::test_merge_question_batches_prefers_later_duplicate_question_numbers -v
```

Expected: FAIL with missing `chunk_items` / `merge_question_batches`.

- [ ] **Step 3: Implement helper functions**

Add these functions in `parser.py` after `_parse_json_content()`:

```python
def chunk_items(items, chunk_size):
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")
    return [items[i:i + chunk_size] for i in range(0, len(items), chunk_size)]


def merge_question_batches(batch_results):
    by_num = {}
    order = []
    for result in batch_results:
        for question in result.get("questions", []):
            question_num = question.get("question_num")
            if question_num is None:
                continue
            if question_num not in by_num:
                order.append(question_num)
            by_num[question_num] = question
    return {"questions": [by_num[num] for num in sorted(order)]}
```

- [ ] **Step 4: Run helper tests to verify pass**

Run:

```bash
cd D:/Claude/gaokao-chem && python -m pytest tests/test_parser_documents.py::DocumentParserTests::test_chunk_items_splits_without_dropping_items tests/test_parser_documents.py::DocumentParserTests::test_merge_question_batches_prefers_later_duplicate_question_numbers -v
```

Expected: PASS.

---

### Task 3: Batch Image API Calls

**Files:**
- Modify: `parser.py`
- Test: `tests/test_parser_documents.py`

- [ ] **Step 1: Write failing batch-call test**

Add this test to `DocumentParserTests`:

```python
    def test_call_mimo_with_image_batches_sends_all_images_in_chunks(self):
        image_urls = [f"data:image/jpeg;base64,{i}" for i in range(25)]
        responses = [
            {"questions": [{"question_num": 1, "stem": "q1"}]},
            {"questions": [{"question_num": 2, "stem": "q2"}]},
            {"questions": [{"question_num": 3, "stem": "q3"}]},
        ]

        with mock.patch.object(parser, "call_mimo", side_effect=responses) as call_mimo:
            result = parser.call_mimo_with_image_batches("paper text", image_urls, batch_size=10)

        self.assertEqual([q["question_num"] for q in result["questions"]], [1, 2, 3])
        self.assertEqual(call_mimo.call_count, 3)
        self.assertEqual(call_mimo.call_args_list[0].kwargs["image_urls"], image_urls[:10])
        self.assertEqual(call_mimo.call_args_list[1].kwargs["image_urls"], image_urls[10:20])
        self.assertEqual(call_mimo.call_args_list[2].kwargs["image_urls"], image_urls[20:])
```

- [ ] **Step 2: Run batch-call test to verify it fails**

Run:

```bash
cd D:/Claude/gaokao-chem && python -m pytest tests/test_parser_documents.py::DocumentParserTests::test_call_mimo_with_image_batches_sends_all_images_in_chunks -v
```

Expected: FAIL with missing `call_mimo_with_image_batches`.

- [ ] **Step 3: Implement batching function**

Add this function in `parser.py` after `merge_question_batches()`:

```python
def call_mimo_with_image_batches(paper_text, image_urls, batch_size=12):
    if not image_urls:
        return call_mimo(paper_text)

    batch_results = []
    batches = chunk_items(image_urls, batch_size)
    for index, batch in enumerate(batches, start=1):
        batch_text = (
            f"{paper_text}\n\n"
            f"Attached images batch {index}/{len(batches)}. "
            "Parse all questions supported by this batch. If a question appears in multiple batches, "
            "return the most complete version using the visible diagrams, tables, equations, and labels."
        )
        result = call_mimo(batch_text, image_urls=batch)
        if result and "error" in result:
            return result
        if result:
            batch_results.append(result)

    return merge_question_batches(batch_results)
```

- [ ] **Step 4: Run batch-call test to verify pass**

Run:

```bash
cd D:/Claude/gaokao-chem && python -m pytest tests/test_parser_documents.py::DocumentParserTests::test_call_mimo_with_image_batches_sends_all_images_in_chunks -v
```

Expected: PASS.

---

### Task 4: Wire Batching into Document Parsing

**Files:**
- Modify: `parser.py:442-484`
- Test: `tests/test_parser_documents.py`

- [ ] **Step 1: Write failing parse integration test**

Add this test to `DocumentParserTests`:

```python
    def test_parse_document_uses_image_batching_for_many_docx_images(self):
        expected = {"questions": [{"question_num": 4, "stem": "装置正确的是"}]}
        images = [f"data:image/jpeg;base64,{i}" for i in range(25)]

        with mock.patch.object(parser, "extract_text_from_word", return_value="题干文字" * 20), \
             mock.patch.object(parser, "extract_docx_embedded_images_as_data_urls", return_value=images), \
             mock.patch.object(parser, "call_mimo_with_image_batches", return_value=expected) as batched, \
             mock.patch.object(parser, "call_mimo") as direct:
            result = parser.parse_document_to_questions("paper.docx")

        self.assertEqual(result["questions"], expected["questions"])
        direct.assert_not_called()
        args, kwargs = batched.call_args
        self.assertIn("DOCX embedded images", args[0])
        self.assertEqual(args[1], images)
```

- [ ] **Step 2: Run parse integration test to verify it fails**

Run:

```bash
cd D:/Claude/gaokao-chem && python -m pytest tests/test_parser_documents.py::DocumentParserTests::test_parse_document_uses_image_batching_for_many_docx_images -v
```

Expected: FAIL because `parse_document_to_questions()` still calls `call_mimo()` directly.

- [ ] **Step 3: Update parse orchestration**

In `parser.py`, replace:

```python
    result = call_mimo(prompt_text, image_urls=image_urls or None)
```

with:

```python
    if image_urls:
        result = call_mimo_with_image_batches(prompt_text, image_urls)
    else:
        result = call_mimo(prompt_text)
```

- [ ] **Step 4: Run parse integration test to verify pass**

Run:

```bash
cd D:/Claude/gaokao-chem && python -m pytest tests/test_parser_documents.py::DocumentParserTests::test_parse_document_uses_image_batching_for_many_docx_images -v
```

Expected: PASS.

---

### Task 5: Regression Suite

**Files:**
- Test: `tests/test_parser_documents.py`
- Test: `tests/test_delete_paper.py`
- Test: `tests/test_admin_upload_documents.py`

- [ ] **Step 1: Run parser tests**

Run:

```bash
cd D:/Claude/gaokao-chem && python -m pytest tests/test_parser_documents.py -v
```

Expected: all parser tests PASS.

- [ ] **Step 2: Run related admin/delete tests**

Run:

```bash
cd D:/Claude/gaokao-chem && python -m pytest tests/test_delete_paper.py tests/test_admin_upload_documents.py -v
```

Expected: all tests PASS.

- [ ] **Step 3: Manual smoke test with existing DOCX**

If `data/uploads/2025-.docx` exists, run:

```bash
cd D:/Claude/gaokao-chem && python - <<'PY'
import os
from parser import extract_docx_embedded_images_as_data_urls
path = 'data/uploads/2025-.docx'
imgs = extract_docx_embedded_images_as_data_urls(path)
print('image_count=', len(imgs))
print('all_data_urls=', all(i.startswith('data:image/') for i in imgs))
PY
```

Expected: prints the actual image count, not capped at 24.

---

## Self-Review

- Spec coverage: plan removes extraction truncation, preserves order/compression, adds batch API calls, and merges all model outputs.
- Placeholder scan: no TBD/TODO placeholders remain.
- Type consistency: helper names `chunk_items`, `merge_question_batches`, and `call_mimo_with_image_batches` are consistently referenced in tests and implementation steps.
