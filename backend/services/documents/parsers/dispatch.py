"""Content-type dispatch for document parsers."""

from urllib.parse import urlsplit

from backend.services.documents.parsers.common import (
    DocumentParseError,
    ParsedDocument,
    normalize_text,
)
from backend.services.documents.parsers.html_parser import parse_html
from backend.services.documents.parsers.pdf_parser import parse_pdf
from backend.services.documents.parsers.xml_parser import parse_jats_xml


def parse_document(
    content: bytes, media_type: str, source_url: str
) -> tuple[str, ParsedDocument]:
    """Parse bytes and return the normalized content type plus clean text."""

    normalized_type = media_type.partition(";")[0].strip().lower()
    path = urlsplit(source_url).path.lower()
    if normalized_type in {"application/xml", "text/xml", "application/jats+xml"}:
        return "xml", parse_jats_xml(content)
    if normalized_type in {"text/html", "application/xhtml+xml"}:
        return "html", parse_html(content)
    if (
        normalized_type == "application/pdf"
        or content.startswith(b"%PDF-")
        or path.endswith(".pdf")
    ):
        return "pdf", parse_pdf(content)
    if normalized_type == "text/plain":
        text = normalize_text(content.decode("utf-8", errors="replace"))
        if not text:
            raise DocumentParseError("Plain-text document is empty")
        return "plain_text", ParsedDocument(title=None, text=text)
    raise DocumentParseError(
        f"Unsupported document content type: {normalized_type or 'missing'}"
    )
