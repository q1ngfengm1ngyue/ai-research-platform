"""Text-layer extraction for ordinary, non-OCR PDF documents."""

from io import BytesIO

from pypdf import PdfReader

from backend.services.documents.parsers.common import (
    DocumentParseError,
    ParsedDocument,
    normalize_text,
)


def parse_pdf(content: bytes) -> ParsedDocument:
    try:
        reader = PdfReader(BytesIO(content), strict=False)
        if reader.is_encrypted and reader.decrypt("") == 0:
            raise DocumentParseError("PDF is encrypted")
        pages = [page.extract_text() or "" for page in reader.pages]
        title_value = reader.metadata.title if reader.metadata else None
    except DocumentParseError:
        raise
    except Exception as exc:
        raise DocumentParseError("PDF could not be parsed") from exc

    text = normalize_text("\n\n".join(pages))
    if not text:
        raise DocumentParseError("PDF contains no extractable text layer")
    title = normalize_text(str(title_value)) if title_value else None
    return ParsedDocument(title=title or None, text=text)
