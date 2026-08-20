"""JATS/XML full-text extraction."""

import xml.etree.ElementTree as ET

from backend.services.documents.parsers.common import (
    DocumentParseError,
    ParsedDocument,
    normalize_text,
)


def parse_jats_xml(content: bytes) -> ParsedDocument:
    try:
        root = ET.fromstring(content)
    except (ET.ParseError, ValueError) as exc:
        raise DocumentParseError("XML document is malformed") from exc

    title_element = _first(root, "article-title")
    title = _element_text(title_element)
    blocks: list[str] = []
    if title:
        blocks.append(title)

    abstract = _first(root, "abstract")
    if abstract is not None:
        abstract_blocks = _section_blocks(abstract)
        if abstract_blocks:
            blocks.extend(["Abstract", *abstract_blocks])

    body = _first(root, "body")
    if body is not None:
        blocks.extend(_section_blocks(body))

    text = normalize_text("\n\n".join(blocks))
    if not text:
        raise DocumentParseError("XML document contains no article text")
    return ParsedDocument(title=title, text=text)


def _section_blocks(container: ET.Element) -> list[str]:
    blocks: list[str] = []
    for element in container.iter():
        name = _local_name(element.tag)
        if name in {"title", "p"}:
            text = _element_text(element)
            if text and (not blocks or text != blocks[-1]):
                blocks.append(text)
    return blocks


def _first(root: ET.Element, local_name: str) -> ET.Element | None:
    return next(
        (element for element in root.iter() if _local_name(element.tag) == local_name),
        None,
    )


def _local_name(tag: str) -> str:
    return tag.rsplit("}", maxsplit=1)[-1]


def _element_text(element: ET.Element | None) -> str | None:
    if element is None:
        return None
    value = " ".join("".join(element.itertext()).split())
    return value or None
