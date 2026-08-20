"""Shared parser results and light text normalization."""

from dataclasses import dataclass
import re
import unicodedata


@dataclass(frozen=True)
class ParsedDocument:
    title: str | None
    text: str


class DocumentParseError(RuntimeError):
    """A safe error raised when downloaded content cannot become useful text."""


def normalize_text(value: str) -> str:
    """Normalize Unicode and whitespace while preserving paragraph boundaries."""

    value = (
        unicodedata.normalize("NFKC", value)
        .replace("\r\n", "\n")
        .replace("\r", "\n")
    )
    value = "".join(
        character
        for character in value
        if character in {"\n", "\t"} or unicodedata.category(character) != "Cc"
    )
    lines = [re.sub(r"[\t\f\v ]+", " ", line).strip() for line in value.split("\n")]
    paragraphs: list[str] = []
    current: list[str] = []
    for line in lines:
        if line:
            current.append(line)
        elif current:
            paragraphs.append(" ".join(current))
            current = []
    if current:
        paragraphs.append(" ".join(current))
    return "\n\n".join(paragraphs).strip()
