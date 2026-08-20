"""Unit tests for XML, HTML, and PDF clean-text parsing."""

from types import SimpleNamespace
import unittest
from unittest.mock import patch

from pypdf.errors import PdfReadError

from backend.services.documents.parsers import DocumentParseError
from backend.services.documents.parsers.html_parser import parse_html
from backend.services.documents.parsers.pdf_parser import parse_pdf
from backend.services.documents.parsers.xml_parser import parse_jats_xml


class XmlParserTests(unittest.TestCase):
    def test_extracts_title_abstract_body_and_multiple_sections(self) -> None:
        parsed = parse_jats_xml(
            b"""<article><front><article-meta><title-group>
            <article-title>Open Science</article-title></title-group>
            <abstract><p>Abstract text.</p></abstract></article-meta></front>
            <body><sec><title>Introduction</title><p>First paragraph.</p></sec>
            <sec><title>Results</title><p>Second <italic>important</italic> paragraph.</p></sec>
            </body></article>"""
        )

        self.assertEqual(parsed.title, "Open Science")
        self.assertIn("Abstract\n\nAbstract text.", parsed.text)
        self.assertIn("Introduction\n\nFirst paragraph.", parsed.text)
        self.assertIn("Results\n\nSecond important paragraph.", parsed.text)

    def test_rejects_malformed_xml(self) -> None:
        with self.assertRaisesRegex(DocumentParseError, "malformed"):
            parse_jats_xml(b"<article><body>")


class HtmlParserTests(unittest.TestCase):
    def test_extracts_readable_text_and_removes_script_style_navigation(self) -> None:
        parsed = parse_html(
            b"""<html><head><title>OA Article</title><style>.x{}</style></head>
            <body><nav>Account login</nav><main><h1>Findings</h1>
            <p>Useful <strong>research</strong> text.</p>
            <script>alert('bad')</script></main></body></html>"""
        )

        self.assertEqual(parsed.title, "OA Article")
        self.assertIn("Findings", parsed.text)
        self.assertIn("Useful research text.", parsed.text)
        self.assertNotIn("Account login", parsed.text)
        self.assertNotIn("alert", parsed.text)


class PdfParserTests(unittest.TestCase):
    @patch("backend.services.documents.parsers.pdf_parser.PdfReader")
    def test_extracts_text_layer_from_parseable_pdf(self, reader_class) -> None:
        reader_class.return_value = SimpleNamespace(
            is_encrypted=False,
            pages=[SimpleNamespace(extract_text=lambda: "Page one text."),
                   SimpleNamespace(extract_text=lambda: "Page two text.")],
            metadata=SimpleNamespace(title="PDF title"),
        )

        parsed = parse_pdf(b"%PDF-test")

        self.assertEqual(parsed.title, "PDF title")
        self.assertIn("Page one text.\n\nPage two text.", parsed.text)

    @patch("backend.services.documents.parsers.pdf_parser.PdfReader")
    def test_reports_unparseable_pdf(self, reader_class) -> None:
        reader_class.side_effect = PdfReadError("broken")

        with self.assertRaisesRegex(DocumentParseError, "could not be parsed"):
            parse_pdf(b"%PDF-broken")


if __name__ == "__main__":
    unittest.main()
