# Two-Stage Parsing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Word/PDF exam parsing more robust by parsing text first, then using small image-only annotation batches to attach image references without failing the whole paper when image parsing times out.

**Architecture:** Keep `parser.py` as the parsing boundary. `parse_document_to_questions()` will extract text and images as it does today, call the model once for text-only questions, then call a new image annotation batch helper that returns lightweight `{question_num, image_refs, visual_note}` records. A merge helper will attach valid image references and optional visual notes to the already-parsed text questions.

**Tech Stack:** Python 3, Flask app backend, `unittest`, `unittest.mock`, `requests`, existing Mimo/OpenAI-compatible API wrapper.

---

## File Structure

- Modify `parser.py`
  - Add `MIMO_TIMEOUT_SECONDS = 180` near the Mimo constants / `call_mimo()` implementation.
  - Add `IMAGE_ANNOTATION_PROMPT` near `EXTRACTION_PROMPT`.
  - Update `call_mimo()` to use `MIMO_TIMEOUT_SECONDS` instead of hard-coded `120`.
  - Add `call_mimo_image_annotation_batches(paper_text, questions, image_urls, batch_size=IMAGE_BATCH_SIZE)`.
  - Add `merge_image_annotations(text_result, annotation_results, image_count)`.
  - Update `parse_document_to_questions()` so image documents do text-only parsing first, then image annotations, then merge.
- Modify `tests/test_parser_documents.py`
  - Add tests for timeout constant, image annotation batching, merge behavior, and parse fallback.
  - Update existing tests that currently expect `parse_document_to_questions()` to call `call_mimo_with_image_batches()` directly.

---

### Task 1: Move API timeout into a constant

**Files:**
- Modify: `parser.py:450-453`
- Test: `tests/test_parser_documents.py`

- [ ] **Step 1: Write the failing test**

Add this test after `test_call_mimo_sends_openai_compatible_multimodal_payload` in `tests/test_parser_documents.py`:

```python
    def test_call_mimo_uses_configured_timeout_constant(self):
        response = mock.Mock()
        response.status_code = 200
        response.json.return_value = {
            "choices": [
                {"message": {"content": '{"questions":[{"question_num":1}]}' }}
            ]
        }

        with mock.patch.object(parser, "MIMO_API_KEY", "test-key"), \
             mock.patch.object(parser.requests, "post", return_value=response) as post:
            parser.call_mimo("question text")

        self.assertEqual(parser.MIMO_TIMEOUT_SECONDS, 180)
        self.assertEqual(post.call_args.kwargs["timeout"], parser.MIMO_TIMEOUT_SECONDS)
```

- [ ] **Step 2: Run the test to verify it fails**

Run:

```powershell
python -m unittest tests.test_parser_documents.DocumentParserTests.test_call_mimo_uses_configured_timeout_constant
```

Expected: FAIL with `AttributeError: module 'parser' has no attribute 'MIMO_TIMEOUT_SECONDS'` or assertion showing timeout is still `120`.

- [ ] **Step 3: Write minimal implementation**

In `parser.py`, add this constant before `call_mimo()`:

```python
MIMO_TIMEOUT_SECONDS = 180
```

Then change the API call in `call_mimo()` from:

```python
        resp = requests.post(MIMO_API_URL, headers=headers, json=payload, timeout=120)
```

to:

```python
        resp = requests.post(MIMO_API_URL, headers=headers, json=payload, timeout=MIMO_TIMEOUT_SECONDS)
```

- [ ] **Step 4: Run the test to verify it passes**

Run:

```powershell
python -m unittest tests.test_parser_documents.DocumentParserTests.test_call_mimo_uses_configured_timeout_constant
```

Expected: PASS.

- [ ] **Step 5: Run the focused parser tests**

Run:

```powershell
python -m unittest tests.test_parser_documents
```

Expected: all tests in `tests.test_parser_documents` pass.

---

### Task 2: Add image annotation merge logic

**Files:**
- Modify: `parser.py:503-548`
- Test: `tests/test_parser_documents.py`

- [ ] **Step 1: Write the failing merge tests**

Add these tests after `test_merge_question_batches_prefers_later_duplicate_question_numbers` in `tests/test_parser_documents.py`:

```python
    def test_merge_image_annotations_adds_valid_image_refs_and_visual_notes(self):
        text_result = {"questions": [
            {"question_num": 1, "stem": "q1", "explanation": "原解析"},
            {"question_num": 2, "stem": "q2", "image_refs": [2]},
        ]}
        annotation_results = [
            {"annotations": [
                {"question_num": 1, "image_refs": [1, 1, 99, "bad"], "visual_note": "图1为实验装置"},
                {"question_num": 2, "image_refs": [2, 3], "visual_note": "图3为曲线"},
                {"question_num": 999, "image_refs": [4], "visual_note": "忽略"},
            ]}
        ]

        merged = parser.merge_image_annotations(text_result, annotation_results, image_count=3)

        self.assertEqual(merged["questions"][0]["image_refs"], [1])
        self.assertIn("原解析", merged["questions"][0]["explanation"])
        self.assertIn("图像信息：图1为实验装置", merged["questions"][0]["explanation"])
        self.assertEqual(merged["questions"][1]["image_refs"], [2, 3])
        self.assertIn("图像信息：图3为曲线", merged["questions"][1]["explanation"])

    def test_merge_image_annotations_keeps_text_result_when_annotations_error(self):
        text_result = {"questions": [{"question_num": 1, "stem": "q1"}]}

        merged = parser.merge_image_annotations(
            text_result,
            [{"error": "API call failed: timeout"}],
            image_count=2,
        )

        self.assertEqual(merged, text_result)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run:

```powershell
python -m unittest tests.test_parser_documents.DocumentParserTests.test_merge_image_annotations_adds_valid_image_refs_and_visual_notes tests.test_parser_documents.DocumentParserTests.test_merge_image_annotations_keeps_text_result_when_annotations_error
```

Expected: FAIL with `AttributeError: module 'parser' has no attribute 'merge_image_annotations'`.

- [ ] **Step 3: Write minimal implementation**

Add this function after `merge_question_batches()` in `parser.py`:

```python
def merge_image_annotations(text_result, annotation_results, image_count):
    """Attach image_refs and visual notes to text-parsed questions."""
    if not text_result or "questions" not in text_result:
        return text_result

    by_num = {
        question.get("question_num"): question
        for question in text_result.get("questions", [])
        if question.get("question_num") is not None
    }

    for result in annotation_results or []:
        if not result or "error" in result:
            continue
        for annotation in result.get("annotations", []):
            question = by_num.get(annotation.get("question_num"))
            if not question:
                continue

            existing_refs = [
                ref for ref in question.get("image_refs", [])
                if isinstance(ref, int) and 1 <= ref <= image_count
            ]
            seen = set(existing_refs)
            merged_refs = list(existing_refs)
            for ref in annotation.get("image_refs") or []:
                if not isinstance(ref, int) or ref < 1 or ref > image_count or ref in seen:
                    continue
                seen.add(ref)
                merged_refs.append(ref)
            if merged_refs:
                question["image_refs"] = merged_refs

            visual_note = (annotation.get("visual_note") or "").strip()
            if visual_note:
                explanation = (question.get("explanation") or "").strip()
                note_text = f"图像信息：{visual_note}"
                question["explanation"] = f"{explanation}\n\n{note_text}" if explanation else note_text

    return text_result
```

- [ ] **Step 4: Run the merge tests to verify they pass**

Run:

```powershell
python -m unittest tests.test_parser_documents.DocumentParserTests.test_merge_image_annotations_adds_valid_image_refs_and_visual_notes tests.test_parser_documents.DocumentParserTests.test_merge_image_annotations_keeps_text_result_when_annotations_error
```

Expected: PASS.

- [ ] **Step 5: Run the focused parser tests**

Run:

```powershell
python -m unittest tests.test_parser_documents
```

Expected: all tests in `tests.test_parser_documents` pass.

---

### Task 3: Add image annotation batch calls

**Files:**
- Modify: `parser.py:504-548`
- Test: `tests/test_parser_documents.py`

- [ ] **Step 1: Write the failing tests**

Add these tests after the merge tests in `tests/test_parser_documents.py`:

```python
    def test_call_mimo_image_annotation_batches_sends_lightweight_annotation_prompt(self):
        image_urls = [f"data:image/jpeg;base64,{i}" for i in range(5)]
        text_result = {"questions": [
            {"question_num": 1, "stem": "第一题"},
            {"question_num": 2, "stem": "第二题"},
        ]}
        responses = [
            {"annotations": [{"question_num": 1, "image_refs": [1], "visual_note": "装置图"}]},
            {"annotations": [{"question_num": 2, "image_refs": [5], "visual_note": "曲线图"}]},
        ]

        with mock.patch.object(parser, "call_mimo", side_effect=responses) as call_mimo:
            result = parser.call_mimo_image_annotation_batches("paper text", text_result, image_urls, batch_size=4)

        self.assertEqual(result, responses)
        self.assertEqual(call_mimo.call_count, 2)
        first_prompt = call_mimo.call_args_list[0].args[0]
        self.assertIn("只输出图片标注", first_prompt)
        self.assertIn("question_num", first_prompt)
        self.assertIn("image_refs", first_prompt)
        self.assertIn("visual_note", first_prompt)
        self.assertEqual(call_mimo.call_args_list[0].kwargs["image_urls"], image_urls[:4])
        self.assertEqual(call_mimo.call_args_list[1].kwargs["image_urls"], image_urls[4:])
        self.assertEqual(call_mimo.call_args_list[0].kwargs["system_prompt"], parser.IMAGE_ANNOTATION_PROMPT)

    def test_call_mimo_image_annotation_batches_returns_error_batch_without_raising(self):
        image_urls = [f"data:image/jpeg;base64,{i}" for i in range(4)]
        text_result = {"questions": [{"question_num": 1, "stem": "第一题"}]}

        with mock.patch.object(parser, "call_mimo", return_value={"error": "API call failed: timeout"}):
            result = parser.call_mimo_image_annotation_batches("paper text", text_result, image_urls, batch_size=4)

        self.assertEqual(result, [{"error": "API call failed: timeout"}])
```

- [ ] **Step 2: Run the tests to verify they fail**

Run:

```powershell
python -m unittest tests.test_parser_documents.DocumentParserTests.test_call_mimo_image_annotation_batches_sends_lightweight_annotation_prompt tests.test_parser_documents.DocumentParserTests.test_call_mimo_image_annotation_batches_returns_error_batch_without_raising
```

Expected: FAIL with `AttributeError: module 'parser' has no attribute 'call_mimo_image_annotation_batches'`.

- [ ] **Step 3: Write minimal implementation**

Add this prompt near `EXTRACTION_PROMPT` in `parser.py`:

```python
IMAGE_ANNOTATION_PROMPT = """
你是高考化学试卷图片标注助手。你只输出图片标注 JSON，不重新解析整张试卷。

任务：根据已解析出的题目列表和当前批次图片，判断每张图片属于哪道题，并概括图片中的关键信息。

输出格式必须是严格 JSON：
{
  "annotations": [
    {
      "question_num": 1,
      "image_refs": [1],
      "visual_note": "图片中的关键实验装置、曲线、表格或结构信息"
    }
  ]
}

规则：
- 只输出 annotations，不输出 questions。
- image_refs 使用文档中的全局图片序号，不是当前批次内序号。
- 无法确定属于哪道题的图片不要输出。
- 不要改写题干、答案或解析。
"""
```

Add this function after `IMAGE_BATCH_SIZE = 4` in `parser.py`:

```python
def call_mimo_image_annotation_batches(paper_text, text_result, image_urls, batch_size=IMAGE_BATCH_SIZE):
    """Ask the model to annotate images against already parsed questions."""
    if not image_urls:
        return []

    question_lines = []
    for question in text_result.get("questions", []):
        question_num = question.get("question_num")
        stem = (question.get("stem") or "").replace("\n", " ")[:120]
        if question_num is not None:
            question_lines.append(f"{question_num}. {stem}")

    batches = chunk_items(list(enumerate(image_urls, start=1)), batch_size)
    annotation_results = []
    for index, batch in enumerate(batches, start=1):
        refs = [seq for seq, _ in batch]
        batch_urls = [url for _, url in batch]
        prompt = (
            "只输出图片标注，不要重新输出题目。\n\n"
            f"已解析题目列表：\n{chr(10).join(question_lines)}\n\n"
            f"当前图片批次 {index}/{len(batches)}，全局图片序号：{refs}\n"
            "请输出 JSON，字段为 annotations/question_num/image_refs/visual_note。"
        )
        logger.info("mimo_image_annotation start index=%s total=%s images=%s", index, len(batches), len(batch_urls))
        batch_start = time.perf_counter()
        result = call_mimo(prompt, image_urls=batch_urls, system_prompt=IMAGE_ANNOTATION_PROMPT)
        logger.info(
            "mimo_image_annotation done index=%s total=%s images=%s elapsed=%.2fs error=%s",
            index,
            len(batches),
            len(batch_urls),
            time.perf_counter() - batch_start,
            bool(result and "error" in result),
        )
        annotation_results.append(result)

    return annotation_results
```

- [ ] **Step 4: Run the annotation batch tests to verify they pass**

Run:

```powershell
python -m unittest tests.test_parser_documents.DocumentParserTests.test_call_mimo_image_annotation_batches_sends_lightweight_annotation_prompt tests.test_parser_documents.DocumentParserTests.test_call_mimo_image_annotation_batches_returns_error_batch_without_raising
```

Expected: PASS.

- [ ] **Step 5: Run the focused parser tests**

Run:

```powershell
python -m unittest tests.test_parser_documents
```

Expected: all tests in `tests.test_parser_documents` pass.

---

### Task 4: Switch document parsing to text-first then image annotations

**Files:**
- Modify: `parser.py:585-676`
- Test: `tests/test_parser_documents.py`

- [ ] **Step 1: Replace old direct image-batch expectations with two-stage expectations**

In `tests/test_parser_documents.py`, replace `test_parse_document_uses_embedded_pdf_images_with_extracted_text` with:

```python
    def test_parse_document_uses_text_first_then_pdf_image_annotations(self):
        text_result = {"questions": [{"question_num": 1, "stem": "text question"}]}
        annotated = {"questions": [{"question_num": 1, "stem": "text question", "image_refs": [1]}]}

        with mock.patch.object(parser, "extract_text_from_pdf", return_value="题干文字" * 20), \
             mock.patch.object(parser, "extract_pdf_embedded_images_as_data_urls", return_value=["data:image/png;base64,embedded"]), \
             mock.patch.object(parser, "render_pdf_pages_as_data_urls") as render_pages, \
             mock.patch.object(parser, "call_mimo", return_value=text_result) as call_mimo, \
             mock.patch.object(parser, "call_mimo_image_annotation_batches", return_value=[{"annotations": []}]) as annotate, \
             mock.patch.object(parser, "merge_image_annotations", return_value=annotated) as merge:
            result = parser.parse_document_to_questions("paper.pdf")

        self.assertEqual(result["questions"], annotated["questions"])
        render_pages.assert_not_called()
        self.assertEqual(call_mimo.call_count, 1)
        self.assertEqual(call_mimo.call_args.args[0], "题干文字" * 20)
        annotate.assert_called_once_with("题干文字" * 20, text_result, ["data:image/png;base64,embedded"])
        merge.assert_called_once_with(text_result, [{"annotations": []}], 1)
```

Replace `test_parse_document_uses_docx_embedded_images_with_extracted_text` with:

```python
    def test_parse_document_uses_text_first_then_docx_image_annotations(self):
        text_result = {"questions": [{"question_num": 4, "stem": "装置正确的是"}]}
        annotated = {"questions": [{"question_num": 4, "stem": "装置正确的是", "image_refs": [1]}]}

        with mock.patch.object(parser, "extract_text_from_word", return_value="题干文字" * 20), \
             mock.patch.object(parser, "extract_docx_embedded_images_as_data_urls",
                               return_value=["data:image/png;base64,docximg"]), \
             mock.patch.object(parser, "call_mimo", return_value=text_result) as call_mimo, \
             mock.patch.object(parser, "call_mimo_image_annotation_batches", return_value=[{"annotations": []}]) as annotate, \
             mock.patch.object(parser, "merge_image_annotations", return_value=annotated) as merge:
            result = parser.parse_document_to_questions("paper.docx")

        self.assertEqual(result["questions"], annotated["questions"])
        self.assertEqual(call_mimo.call_count, 1)
        self.assertEqual(call_mimo.call_args.args[0], "题干文字" * 20)
        annotate.assert_called_once_with("题干文字" * 20, text_result, ["data:image/png;base64,docximg"])
        merge.assert_called_once_with(text_result, [{"annotations": []}], 1)
```

Replace `test_parse_document_uses_image_batching_for_many_docx_images` with:

```python
    def test_parse_document_uses_image_annotation_batching_for_many_docx_images(self):
        text_result = {"questions": [{"question_num": 4, "stem": "装置正确的是"}]}
        annotated = {"questions": [{"question_num": 4, "stem": "装置正确的是", "image_refs": [1, 2]}]}
        images = [f"data:image/jpeg;base64,{i}" for i in range(25)]

        with mock.patch.object(parser, "extract_text_from_word", return_value="题干文字" * 20), \
             mock.patch.object(parser, "extract_docx_embedded_images_as_data_urls", return_value=images), \
             mock.patch.object(parser, "call_mimo", return_value=text_result) as call_mimo, \
             mock.patch.object(parser, "call_mimo_image_annotation_batches", return_value=[{"annotations": []}]) as annotate, \
             mock.patch.object(parser, "merge_image_annotations", return_value=annotated) as merge:
            result = parser.parse_document_to_questions("paper.docx")

        self.assertEqual(result["questions"], annotated["questions"])
        self.assertEqual(call_mimo.call_count, 1)
        annotate.assert_called_once_with("题干文字" * 20, text_result, images)
        merge.assert_called_once_with(text_result, [{"annotations": []}], 25)
        self.assertEqual(result["images"], images)
        self.assertEqual(result["image_source"], "DOCX embedded images")
```

- [ ] **Step 2: Add fallback test for image-stage failure**

Add this test near the parse document tests in `tests/test_parser_documents.py`:

```python
    def test_parse_document_keeps_text_questions_when_image_annotation_fails(self):
        text_result = {"questions": [{"question_num": 4, "stem": "装置正确的是"}]}
        images = ["data:image/jpeg;base64,1"]

        with mock.patch.object(parser, "extract_text_from_word", return_value="题干文字" * 20), \
             mock.patch.object(parser, "extract_docx_embedded_images_as_data_urls", return_value=images), \
             mock.patch.object(parser, "call_mimo", return_value=text_result), \
             mock.patch.object(parser, "call_mimo_image_annotation_batches", return_value=[{"error": "API call failed: timeout"}]):
            result = parser.parse_document_to_questions("paper.docx")

        self.assertEqual(result["questions"], text_result["questions"])
        self.assertEqual(result["images"], images)
        self.assertEqual(result["image_source"], "DOCX embedded images")
```

- [ ] **Step 3: Run the parse tests to verify they fail against old flow**

Run:

```powershell
python -m unittest tests.test_parser_documents.DocumentParserTests.test_parse_document_uses_text_first_then_pdf_image_annotations tests.test_parser_documents.DocumentParserTests.test_parse_document_uses_text_first_then_docx_image_annotations tests.test_parser_documents.DocumentParserTests.test_parse_document_uses_image_annotation_batching_for_many_docx_images tests.test_parser_documents.DocumentParserTests.test_parse_document_keeps_text_questions_when_image_annotation_fails
```

Expected: FAIL because `parse_document_to_questions()` still calls `call_mimo_with_image_batches()` for image documents.

- [ ] **Step 4: Write minimal parser flow implementation**

In `parser.py`, replace the block from `prompt_text = text` through the `if "error" in result:` check in `parse_document_to_questions()` with:

```python
    ai_start = time.perf_counter()
    result = call_mimo(text)
    logger.info(
        "parse_document text_ai_done file=%s kind=%s elapsed=%.2fs error=%s",
        os.path.basename(filepath),
        kind,
        time.perf_counter() - ai_start,
        bool(result and "error" in result),
    )
    if not result:
        return {"error": "AI 解析失败，请重试"}
    if "error" in result:
        return result

    if image_urls:
        image_ai_start = time.perf_counter()
        annotation_results = call_mimo_image_annotation_batches(text, result, image_urls)
        result = merge_image_annotations(result, annotation_results, len(image_urls))
        logger.info(
            "parse_document image_ai_done file=%s kind=%s images=%s batches=%s elapsed=%.2fs annotation_errors=%s",
            os.path.basename(filepath),
            kind,
            len(image_urls),
            batches,
            time.perf_counter() - image_ai_start,
            sum(1 for item in annotation_results if item and "error" in item),
        )
```

Keep the existing `questions = result.get("questions", [])`, final `parse_document done` log, and return block unchanged.

- [ ] **Step 5: Run the parse tests to verify they pass**

Run:

```powershell
python -m unittest tests.test_parser_documents.DocumentParserTests.test_parse_document_uses_text_first_then_pdf_image_annotations tests.test_parser_documents.DocumentParserTests.test_parse_document_uses_text_first_then_docx_image_annotations tests.test_parser_documents.DocumentParserTests.test_parse_document_uses_image_annotation_batching_for_many_docx_images tests.test_parser_documents.DocumentParserTests.test_parse_document_keeps_text_questions_when_image_annotation_fails
```

Expected: PASS.

- [ ] **Step 6: Update logging test if necessary**

Run:

```powershell
python -m unittest tests.test_parser_documents.DocumentParserTests.test_parse_document_logs_timing_diagnostics_for_docx_images
```

Expected: PASS if it only checks generic start/done/images/batches logs. If it still expects `parse_document ai_done`, replace that assertion with checks for both `parse_document text_ai_done` and `parse_document image_ai_done`.

---

### Task 5: Preserve image-only scan PDF behavior

**Files:**
- Modify: `parser.py:631-658`
- Test: `tests/test_parser_documents.py`

- [ ] **Step 1: Add a failing test for image-only PDF scans**

Replace `test_parse_document_renders_pdf_pages_only_when_text_and_embedded_images_are_missing` with:

```python
    def test_parse_document_renders_pdf_pages_and_uses_legacy_image_batching_when_text_is_missing(self):
        expected = {"questions": [{"question_num": 1, "stem": "image question"}]}

        with mock.patch.object(parser, "extract_text_from_pdf", return_value=""), \
             mock.patch.object(parser, "extract_pdf_embedded_images_as_data_urls", return_value=[]), \
             mock.patch.object(parser, "render_pdf_pages_as_data_urls", return_value=["data:image/png;base64,abc"]), \
             mock.patch.object(parser, "call_mimo_with_image_batches", return_value=expected) as batched, \
             mock.patch.object(parser, "call_mimo_image_annotation_batches") as annotate:
            result = parser.parse_document_to_questions("scan.pdf")

        self.assertEqual(result["questions"], expected["questions"])
        annotate.assert_not_called()
        args, kwargs = batched.call_args
        self.assertIn("PDF page images", args[0])
        self.assertEqual(args[1], ["data:image/png;base64,abc"])
```

- [ ] **Step 2: Run the test to verify it fails if text-only parsing is attempted on empty text**

Run:

```powershell
python -m unittest tests.test_parser_documents.DocumentParserTests.test_parse_document_renders_pdf_pages_and_uses_legacy_image_batching_when_text_is_missing
```

Expected: FAIL until `parse_document_to_questions()` preserves the existing image-only fallback path.

- [ ] **Step 3: Implement image-only fallback path**

In `parse_document_to_questions()`, after the existing short-text validation and before text-first AI parsing, add:

```python
    if not text.strip() and image_urls:
        prompt_text = (
            f"{image_source} are attached. "
            "Use them to recover diagrams, equations, tables, and visual question content."
        )
        ai_start = time.perf_counter()
        result = call_mimo_with_image_batches(prompt_text, image_urls)
        logger.info(
            "parse_document image_only_ai_done file=%s kind=%s images=%s batches=%s elapsed=%.2fs error=%s",
            os.path.basename(filepath),
            kind,
            len(image_urls),
            batches,
            time.perf_counter() - ai_start,
            bool(result and "error" in result),
        )
        if not result:
            return {"error": "AI 解析失败，请重试"}
        if "error" in result:
            return result
        questions = result.get("questions", [])
        logger.info(
            "parse_document done file=%s kind=%s text_chars=%s images=%s batches=%s questions=%s elapsed=%.2fs",
            os.path.basename(filepath),
            kind,
            len(text),
            len(image_urls),
            batches,
            len(questions),
            time.perf_counter() - total_start,
        )
        return {
            "questions": questions,
            "raw_text": text[:5000],
            "images": image_urls,
            "image_source": image_source,
        }
```

- [ ] **Step 4: Run the image-only test to verify it passes**

Run:

```powershell
python -m unittest tests.test_parser_documents.DocumentParserTests.test_parse_document_renders_pdf_pages_and_uses_legacy_image_batching_when_text_is_missing
```

Expected: PASS.

- [ ] **Step 5: Run all parser document tests**

Run:

```powershell
python -m unittest tests.test_parser_documents
```

Expected: all tests in `tests.test_parser_documents` pass.

---

### Task 6: Full verification for parser/image persistence integration

**Files:**
- Verify: `tests/test_parser_documents.py`
- Verify: `tests/test_question_images.py`
- Verify: `tests/test_frontend_images.py`

- [ ] **Step 1: Run parser tests**

Run:

```powershell
python -m unittest tests.test_parser_documents
```

Expected: all tests pass.

- [ ] **Step 2: Run image persistence/API tests**

Run:

```powershell
python -m unittest tests.test_question_images tests.test_frontend_images
```

Expected: all tests pass.

- [ ] **Step 3: Run all tests**

Run:

```powershell
python -m unittest discover tests
```

Expected: all tests pass.

- [ ] **Step 4: Inspect git diff before reporting**

Run:

```powershell
git diff -- parser.py tests/test_parser_documents.py
```

Expected: diff shows only two-stage parser, annotation merge, timeout constant, and matching tests.

---

## Self-Review

**Spec coverage:**
- Text-first parsing is covered by Task 4.
- Image annotation batches are covered by Task 3.
- Merge into questions is covered by Task 2.
- Image-stage failure preserving text questions is covered by Task 4.
- Timeout constant is covered by Task 1.
- Image-only scanned PDF fallback is covered by Task 5.
- Full regression verification is covered by Task 6.

**Placeholder scan:** No TBD/TODO/fill-in-later placeholders remain. Every test and implementation step includes concrete code or exact commands.

**Type consistency:** The plan consistently uses `annotations`, `question_num`, `image_refs`, `visual_note`, `MIMO_TIMEOUT_SECONDS`, `IMAGE_ANNOTATION_PROMPT`, `call_mimo_image_annotation_batches()`, and `merge_image_annotations()`.
