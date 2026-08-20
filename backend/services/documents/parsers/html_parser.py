"""Conservative HTML-to-text extraction for open-access article pages."""

from html.parser import HTMLParser

from backend.services.documents.parsers.common import (
    DocumentParseError,
    ParsedDocument,
    normalize_text,
)


class _ArticleHTMLParser(HTMLParser):
    ignored_tags = {"script", "style", "nav", "header", "footer", "aside", "noscript"}
    block_tags = {
        "article",
        "main",
        "section",
        "div",
        "p",
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
        "li",
        "blockquote",
        "br",
        "tr",
    }

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.ignored_depth = 0
        self.in_title = False
        self.title_parts: list[str] = []
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        del attrs
        tag = tag.lower()
        if tag in self.ignored_tags:
            self.ignored_depth += 1
        if tag == "title" and not self.ignored_depth:
            self.in_title = True
        if tag in self.block_tags and not self.ignored_depth:
            self.parts.append("\n\n")

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag == "title":
            self.in_title = False
        if tag in self.block_tags and not self.ignored_depth:
            self.parts.append("\n\n")
        if tag in self.ignored_tags and self.ignored_depth:
            self.ignored_depth -= 1

    def handle_data(self, data: str) -> None:
        if self.ignored_depth or not data.strip():
            return
        if self.in_title:
            self.title_parts.append(data)
            return
        self.parts.append(data)


def parse_html(content: bytes) -> ParsedDocument:
    parser = _ArticleHTMLParser()
    try:
        parser.feed(content.decode("utf-8", errors="replace"))
        parser.close()
    except (UnicodeError, ValueError) as exc:
        raise DocumentParseError("HTML document could not be parsed") from exc

    title = normalize_text(" ".join(parser.title_parts)) or None
    text = normalize_text(" ".join(parser.parts))
    if not text:
        raise DocumentParseError("HTML document contains no readable text")
    return ParsedDocument(title=title, text=text)
