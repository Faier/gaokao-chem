import os
import tempfile
import unittest
from unittest import mock

import parser


class DocumentParserTests(unittest.TestCase):
    def test_extraction_prompt_prefers_document_answers_and_explanations(self):
        self.assertIn("文档中已有答案或解析时", parser.EXTRACTION_PROMPT)
        self.assertIn("必须以文档原文为准", parser.EXTRACTION_PROMPT)
        self.assertIn("不要改写、替换或重新推断", parser.EXTRACTION_PROMPT)

    def test_choose_best_pdf_text_prefers_chemistry_rich_extraction(self):
        poor = "是一种常见燃料，可以用于火箭助推器。已知：\n①\n②\n③\n则 为\nA."
        rich = (
            "N2H4是一种常见燃料，可以用于火箭助推器。已知：\n"
            "①2NH3(g)+3N2O(g)=4N2(g)+3H2O(l) ΔH1=akJ/mol\n"
            "②N2O(g)+3H2(g)=N2H4(l)+H2O(l) ΔH2=bkJ/mol\n"
            "③N2H4(l)+9H2(g)+4O2(g)=2NH3(g)+8H2O(l) ΔH3=ckJ/mol\n"
            "则N2H4(l)+O2(g)=N2(g)+2H2O(l) ΔH为\n"
            "A. 1/4(a+3b-c)\nB. 1/4(a-3b+c)\nC. (a-3b+c)\nD. (a+3b-c)"
        )

        self.assertEqual(parser.choose_best_pdf_text([poor, rich]), rich)

    def test_document_extension_detection_supports_pdf_doc_and_docx(self):
        self.assertEqual(parser.get_document_kind("paper.PDF"), "pdf")
        self.assertEqual(parser.get_document_kind("paper.doc"), "word")
        self.assertEqual(parser.get_document_kind("paper.docx"), "word")
        self.assertIsNone(parser.get_document_kind("paper.txt"))

    def test_parse_document_uses_embedded_pdf_images_with_extracted_text(self):
        expected = {"questions": [{"question_num": 1, "stem": "image question"}]}

        with mock.patch.object(parser, "extract_text_from_pdf", return_value="题干文字" * 20), \
             mock.patch.object(parser, "extract_pdf_embedded_images_as_data_urls", return_value=["data:image/png;base64,embedded"]), \
             mock.patch.object(parser, "render_pdf_pages_as_data_urls") as render_pages, \
             mock.patch.object(parser, "call_mimo", return_value=expected) as call_mimo:
            result = parser.parse_document_to_questions("paper.pdf")

        self.assertEqual(result["questions"], expected["questions"])
        render_pages.assert_not_called()
        args, kwargs = call_mimo.call_args
        self.assertIn("PDF embedded images", args[0])
        self.assertEqual(kwargs["image_urls"], ["data:image/png;base64,embedded"])

    def test_parse_document_renders_pdf_pages_only_when_text_and_embedded_images_are_missing(self):
        expected = {"questions": [{"question_num": 1, "stem": "image question"}]}

        with mock.patch.object(parser, "extract_text_from_pdf", return_value=""), \
             mock.patch.object(parser, "extract_pdf_embedded_images_as_data_urls", return_value=[]), \
             mock.patch.object(parser, "render_pdf_pages_as_data_urls", return_value=["data:image/png;base64,abc"]), \
             mock.patch.object(parser, "call_mimo", return_value=expected) as call_mimo:
            result = parser.parse_document_to_questions("scan.pdf")

        self.assertEqual(result["questions"], expected["questions"])
        args, kwargs = call_mimo.call_args
        self.assertIn("PDF page images", args[0])
        self.assertEqual(kwargs["image_urls"], ["data:image/png;base64,abc"])

    def test_call_mimo_sends_openai_compatible_multimodal_payload(self):
        response = mock.Mock()
        response.status_code = 200
        response.json.return_value = {
            "choices": [
                {"message": {"content": '{"questions":[{"question_num":1}]}' }}
            ]
        }

        with mock.patch.object(parser, "MIMO_API_KEY", "test-key"), \
             mock.patch.object(parser.requests, "post", return_value=response) as post:
            result = parser.call_mimo("question text", image_urls=["data:image/png;base64,abc"])

        self.assertEqual(result["questions"][0]["question_num"], 1)
        payload = post.call_args.kwargs["json"]
        self.assertEqual(payload["model"], parser.MIMO_MODEL)
        content = payload["messages"][1]["content"]
        self.assertEqual(content[0]["type"], "text")
        self.assertEqual(content[1]["type"], "image_url")

    def test_extract_text_from_docx_reads_paragraphs_and_tables(self):
        try:
            from docx import Document
        except ImportError:
            self.skipTest("python-docx is not installed")

        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "paper.docx")
            doc = Document()
            doc.add_paragraph("第一题")
            table = doc.add_table(rows=1, cols=2)
            table.cell(0, 0).text = "A"
            table.cell(0, 1).text = "正确"
            doc.save(path)

            text = parser.extract_text_from_word(path)

        self.assertIn("第一题", text)
        self.assertIn("A", text)
        self.assertIn("正确", text)


if __name__ == "__main__":
    unittest.main()
