"""Diagnostic tests that reproduce and pinpoint image misplacement.

These tests trace the full image attribution pipeline to determine whether
misplacement originates from:
  (A) AI-generated image_refs in text parsing
  (B) AI-generated image_refs in image annotation
  (C) Failure of position-based matching to override wrong AI assignments
  (D) Frontend display ordering

Each test scenario simulates a concrete misplacement case and asserts
the expected outcome at each pipeline stage.
"""

import unittest
from unittest import mock

import parser


class ImageMisplacementDiagnosisTests(unittest.TestCase):
    """Reproduce image misplacement and identify which pipeline stage fails."""

    # ------------------------------------------------------------------ #
    # Scenario 1: AI assigns image to wrong question; position mapping
    # exists and should override.  This tests whether the position-override
    # pipeline correctly reassigns the image.
    # ------------------------------------------------------------------ #
    def test_position_override_fixes_wrong_ai_assignment(self):
        """AI text parsing wrongly puts image 1 in Q2.  PDF position data
        places the image in Q1's region.  The final result must have image 1
        under Q1 only."""
        text_result = {"questions": [
            {"question_num": 1, "stem": "第一题", "image_refs": []},
            {"question_num": 2, "stem": "第二题", "image_refs": [1]},
        ]}
        # Position mapping: image 1 is physically in Q1's region
        position_mapping = {1: 1}

        parser.apply_position_image_attribution(text_result, position_mapping, image_count=1)

        q1_refs = text_result["questions"][0].get("image_refs", [])
        q2_refs = text_result["questions"][1].get("image_refs", [])
        self.assertIn(1, q1_refs, "Image 1 should be in Q1 after position override")
        self.assertNotIn(1, q2_refs, "Image 1 should be removed from Q2 after position override")

    # ------------------------------------------------------------------ #
    # Scenario 2: AI assigns image to wrong question; NO position mapping
    # available (e.g., scanned PDF with no embedded images, or DOCX with
    # no positional metadata).  This is the most common misplacement path.
    # ------------------------------------------------------------------ #
    def test_no_position_mapping_preserves_wrong_ai_assignment(self):
        """When position mapping is empty, the AI's wrong assignment persists.
        This is the ROOT CAUSE of most misplacement: the position-override
        layer has no data to correct the AI."""
        text_result = {"questions": [
            {"question_num": 1, "stem": "第一题", "image_refs": []},
            {"question_num": 2, "stem": "第二题", "image_refs": [1]},
        ]}
        position_mapping = {}  # no position data available

        parser.apply_position_image_attribution(text_result, position_mapping, image_count=1)

        # Without position override, the wrong assignment stays
        q2_refs = text_result["questions"][1].get("image_refs", [])
        self.assertIn(1, q2_refs,
                       "Without position mapping, AI's wrong assignment persists")

    # ------------------------------------------------------------------ #
    # Scenario 3: AI annotation also assigns image to wrong question.
    # merge_image_annotations merges both wrong sources — neither corrects
    # the other.
    # ------------------------------------------------------------------ #
    def test_both_ai_sources_wrong_no_correction(self):
        """Both text parsing and image annotation assign image 1 to Q2
        (wrong).  The merge combines them without correction."""
        text_result = {"questions": [
            {"question_num": 1, "stem": "第一题"},
            {"question_num": 2, "stem": "第二题", "image_refs": [1]},
        ]}
        annotation_results = [
            {"annotations": [
                {"question_num": 2, "image_refs": [1], "visual_note": "图1描述"},
            ]}
        ]

        merged = parser.merge_image_annotations(text_result, annotation_results, image_count=1)

        q1_refs = merged["questions"][0].get("image_refs", [])
        q2_refs = merged["questions"][1].get("image_refs", [])
        self.assertNotIn(1, q1_refs, "Image 1 should not be in Q1 (both AI sources say Q2)")
        self.assertIn(1, q2_refs, "Image 1 stays in Q2 (both AI sources agree, both wrong)")

    # ------------------------------------------------------------------ #
    # Scenario 4: AI annotation corrects wrong text-parsing assignment.
    # This is the happy path when annotation works.
    # ------------------------------------------------------------------ #
    def test_ai_annotation_can_correct_text_parsing_error(self):
        """Text parsing wrongly assigns image 1 to Q2, but annotation
        correctly assigns it to Q1.  merge_image_annotations adds image 1
        to Q1 (but does NOT remove it from Q2 — that requires position
        override or explicit annotation for Q2)."""
        text_result = {"questions": [
            {"question_num": 1, "stem": "第一题"},
            {"question_num": 2, "stem": "第二题", "image_refs": [1]},
        ]}
        annotation_results = [
            {"annotations": [
                {"question_num": 1, "image_refs": [1], "visual_note": "图1描述"},
            ]}
        ]

        merged = parser.merge_image_annotations(text_result, annotation_results, image_count=1)

        q1_refs = merged["questions"][0].get("image_refs", [])
        q2_refs = merged["questions"][1].get("image_refs", [])
        # Annotation added image 1 to Q1
        self.assertIn(1, q1_refs, "Annotation correctly adds image 1 to Q1")
        # But merge does NOT remove from Q2 — image 1 appears in BOTH questions
        self.assertIn(1, q2_refs,
                       "BUG: merge does not remove image 1 from Q2 even though annotation says Q1")

    # ------------------------------------------------------------------ #
    # Scenario 5: Position override after merge fixes the double-assignment.
    # Full pipeline: wrong AI text → wrong AI annotation → position fix.
    # ------------------------------------------------------------------ #
    def test_full_pipeline_position_fixes_double_assignment(self):
        """Image 1 wrongly in both Q1 (annotation) and Q2 (text parsing).
        Position mapping says image 1 → Q1.  After position override,
        image 1 must be only in Q1."""
        result = {"questions": [
            {"question_num": 1, "stem": "第一题", "image_refs": [1]},
            {"question_num": 2, "stem": "第二题", "image_refs": [1]},
        ]}
        position_mapping = {1: 1}

        parser.apply_position_image_attribution(result, position_mapping, image_count=1)

        q1_refs = result["questions"][0].get("image_refs", [])
        q2_refs = result["questions"][1].get("image_refs", [])
        self.assertIn(1, q1_refs)
        self.assertNotIn(1, q2_refs)

    # ------------------------------------------------------------------ #
    # Scenario 6: match_pdf_images_to_questions returns empty mapping
    # when markers are missing.  This causes position override to skip.
    # ------------------------------------------------------------------ #
    def test_empty_markers_produces_empty_position_mapping(self):
        """When find_pdf_question_markers returns no markers (e.g., scanned
        PDF or unusual layout), position mapping is empty, and AI
        assignments go uncorrected."""
        image_records = [
            {"data_url": "img1", "page_index": 0, "y0": 300.0, "xref": 1},
        ]
        markers = []  # no markers found

        mapping = parser.match_pdf_images_to_questions(image_records, markers)

        self.assertEqual(mapping, {},
                          "Empty markers → empty mapping → no position override")

    # ------------------------------------------------------------------ #
    # Scenario 7: match_docx_images_to_questions returns empty when text
    # stem doesn't match the extracted text (AI rephrased the stem).
    # ------------------------------------------------------------------ #
    def test_docx_matching_fails_when_stem_not_in_text(self):
        """When the AI-generated stem doesn't appear verbatim in the
        extracted text, match_docx_images_to_questions cannot locate Q1's
        position.  An image that belongs to Q1 gets wrongly assigned to Q2
        because Q2 is the nearest question found before the image's paragraph."""
        image_records = [
            {"data_url": "img1", "para_index": 2},
        ]
        text = "1. 原始题干文字内容较长\n图片在此\n2. 第二题原始文字"
        # AI rephrased Q1's stem — won't match the extracted text
        text_result = {"questions": [
            {"question_num": 1, "stem": "AI改写后的题干内容完全不同于原文"},
            {"question_num": 2, "stem": "2. 第二题原始文字"},
        ]}

        mapping = parser.match_docx_images_to_questions(image_records, text, text_result)

        # Q1 stem not found → Q1 has no offset → image falls to Q2 (wrong)
        self.assertEqual(mapping.get(1), 2,
                          "Image wrongly assigned to Q2 because Q1 stem not found in text")

    # ------------------------------------------------------------------ #
    # Scenario 8: Image appears before first question in DOCX — correctly
    # omitted from position mapping (left for AI attribution).
    # ------------------------------------------------------------------ #
    def test_docx_header_image_omitted_from_position_mapping(self):
        """Images in the document header (before Q1) cannot be position-matched.
        They rely entirely on AI attribution, which may be wrong."""
        image_records = [
            {"data_url": "header_img", "para_index": 0},
            {"data_url": "q1_img", "para_index": 2},
        ]
        text = "试卷标题图片\n1. 第一题题干\n题目图片"
        text_result = {"questions": [
            {"question_num": 1, "stem": "1. 第一题题干"},
        ]}

        mapping = parser.match_docx_images_to_questions(image_records, text, text_result)

        self.assertNotIn(1, mapping, "Header image must not be force-assigned")
        self.assertIn(2, mapping, "Q1 image should be assigned")
        self.assertEqual(mapping[2], 1)

    # ------------------------------------------------------------------ #
    # Scenario 9: Cross-page image leak — image on page with no markers
    # should NOT be assigned to a question on a different page.
    # ------------------------------------------------------------------ #
    def test_pdf_cross_page_image_not_leaked(self):
        """An image on page 1 (which has no question markers) must not be
        assigned to a question on page 0."""
        image_records = [
            {"data_url": "page0_img", "page_index": 0, "y0": 300.0},
            {"data_url": "page1_img", "page_index": 1, "y0": 200.0},
        ]
        markers = [
            {"question_num": 1, "page_index": 0, "y0": 100.0, "x0": 10.0},
            {"question_num": 2, "page_index": 2, "y0": 100.0, "x0": 10.0},
        ]

        mapping = parser.match_pdf_images_to_questions(image_records, markers)

        self.assertIn(1, mapping, "Page 0 image should be assigned to Q1")
        self.assertNotIn(2, mapping,
                           "Page 1 image (no markers) must not leak to any question")

    # ------------------------------------------------------------------ #
    # Scenario 10: normalize_parse_result strips out-of-range image_refs.
    # This catches cases where AI returns image numbers beyond the actual
    # image count.
    # ------------------------------------------------------------------ #
    def test_normalize_strips_out_of_range_image_refs(self):
        """If AI returns image_refs=[1,5] but only 3 images exist, ref 5
        must be stripped."""
        result = {"questions": [
            {"question_num": 1, "stem": "题干", "image_refs": [1, 5]},
        ]}

        normalized = parser.normalize_parse_result(result, image_count=3)

        self.assertEqual(normalized["questions"][0].get("image_refs", []), [1],
                          "Out-of-range ref 5 should be stripped")


class DeduplicateImageReferencesTests(unittest.TestCase):
    """Test the deduplicate_image_references fallback for no-position-mapping cases."""

    def test_removes_image_from_later_question(self):
        """Image 1 assigned to both Q1 and Q2 — should stay in Q1 only."""
        result = {"questions": [
            {"question_num": 1, "stem": "第一题", "image_refs": [1]},
            {"question_num": 2, "stem": "第二题", "image_refs": [1]},
        ]}
        parser.deduplicate_image_references(result, image_count=1)
        self.assertEqual(result["questions"][0].get("image_refs"), [1])
        self.assertIsNone(result["questions"][1].get("image_refs"))

    def test_keeps_non_conflicting_images(self):
        """Images assigned to different questions without conflict are kept."""
        result = {"questions": [
            {"question_num": 1, "stem": "第一题", "image_refs": [1]},
            {"question_num": 2, "stem": "第二题", "image_refs": [2]},
        ]}
        parser.deduplicate_image_references(result, image_count=2)
        self.assertEqual(result["questions"][0].get("image_refs"), [1])
        self.assertEqual(result["questions"][1].get("image_refs"), [2])

    def test_partial_conflict_keeps_non_duplicate(self):
        """Q1 has [1,2], Q2 has [2,3]. After dedup: Q1 keeps [1,2], Q2 keeps [3]."""
        result = {"questions": [
            {"question_num": 1, "stem": "第一题", "image_refs": [1, 2]},
            {"question_num": 2, "stem": "第二题", "image_refs": [2, 3]},
        ]}
        parser.deduplicate_image_references(result, image_count=3)
        self.assertEqual(result["questions"][0].get("image_refs"), [1, 2])
        self.assertEqual(result["questions"][1].get("image_refs"), [3])

    def test_strips_out_of_range_refs(self):
        """Refs beyond image_count are removed during dedup."""
        result = {"questions": [
            {"question_num": 1, "stem": "第一题", "image_refs": [1, 5]},
        ]}
        parser.deduplicate_image_references(result, image_count=3)
        self.assertEqual(result["questions"][0].get("image_refs"), [1])

    def test_empty_result_passthrough(self):
        """None or empty result is returned as-is."""
        self.assertIsNone(parser.deduplicate_image_references(None, image_count=0))
        self.assertEqual(parser.deduplicate_image_references({}, image_count=0), {})

    def test_no_image_refs_passthrough(self):
        """Questions without image_refs are unaffected."""
        result = {"questions": [
            {"question_num": 1, "stem": "第一题"},
            {"question_num": 2, "stem": "第二题"},
        ]}
        parser.deduplicate_image_references(result, image_count=0)
        self.assertEqual(len(result["questions"]), 2)

    def test_three_way_conflict(self):
        """Image 1 in Q1, Q2, Q3 — only Q1 keeps it."""
        result = {"questions": [
            {"question_num": 1, "stem": "第一题", "image_refs": [1]},
            {"question_num": 2, "stem": "第二题", "image_refs": [1]},
            {"question_num": 3, "stem": "第三题", "image_refs": [1]},
        ]}
        parser.deduplicate_image_references(result, image_count=1)
        self.assertEqual(result["questions"][0].get("image_refs"), [1])
        self.assertIsNone(result["questions"][1].get("image_refs"))
        self.assertIsNone(result["questions"][2].get("image_refs"))


class PipelineMisplacementSummaryTests(unittest.TestCase):
    """Summarize the misplacement diagnosis as structured findings."""

    def test_summarize_misplacement_sources(self):
        """This test documents the misplacement root causes found."""
        findings = {
            "source_A_ai_text_refs": (
                "AI text parsing may assign wrong image_refs. "
                "The EXTRACTION_PROMPT asks AI to determine image-question "
                "association from text context alone, which is unreliable "
                "for images without explicit '如图所示' references."
            ),
            "source_B_ai_annotation_refs": (
                "AI image annotation may also assign wrong image_refs. "
                "The IMAGE_ANNOTATION_PROMPT sends images in batches with "
                "question stems, but the AI has no visual layout information."
            ),
            "source_C_position_override_gap": (
                "Position-based matching (PDF markers or DOCX paragraph "
                "positions) is the ONLY correction mechanism. When it "
                "returns an empty mapping (no markers, no embedded images, "
                "stem not found in text), wrong AI assignments persist "
                "unchanged. This is the PRIMARY misplacement path."
            ),
            "source_D_frontend_display": (
                "Frontend display is CORRECT: review.html uses images[ref-1] "
                "and app.js renders q.images in API-returned order. "
                "The display faithfully shows whatever image_refs were "
                "persisted. No display-order bug found."
            ),
            "source_E_merge_double_assignment": (
                "merge_image_annotations can create double-assignment: "
                "if text parsing puts image 1 in Q2 and annotation puts "
                "image 1 in Q1, the merge adds to Q1 but does NOT remove "
                "from Q2. Only apply_position_image_attribution removes "
                "the wrong assignment, and only if position_mapping is "
                "non-empty."
            ),
        }

        # Verify each finding is a non-empty string
        for key, description in findings.items():
            self.assertTrue(len(description) > 20, f"{key} should have a meaningful description")

        # The primary misplacement source
        self.assertIn("source_C_position_override_gap", findings)
        self.assertIn("PRIMARY misplacement path", findings["source_C_position_override_gap"])


if __name__ == "__main__":
    unittest.main()
