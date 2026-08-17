"""Unified data structures shared by all literature providers."""

from typing import Literal

from pydantic import BaseModel, Field


class LiteratureItem(BaseModel):
    """Provider-independent metadata for one scholarly work."""

    id: str
    source: Literal["pubmed", "openalex"]
    title: str | None = None
    authors: list[str] = Field(default_factory=list)
    abstract: str | None = None
    publication_date: str | None = None
    year: int | None = None
    journal: str | None = None
    doi: str | None = None
    url: str | None = None


class LiteratureSearchResponse(BaseModel):
    """Response envelope returned by the literature search endpoint."""

    query: str
    source: Literal["pubmed", "openalex", "all"]
    count: int
    results: list[LiteratureItem]
    warnings: list[str] = Field(default_factory=list)
