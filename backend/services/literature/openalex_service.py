"""OpenAlex Works integration and metadata parsing."""

import logging
import os
import re
from typing import Any

import httpx

from backend.schemas.literature import LiteratureItem


logger = logging.getLogger(__name__)

WORKS_URL = "https://api.openalex.org/works"
REQUEST_TIMEOUT = httpx.Timeout(20.0, connect=8.0)


class OpenAlexServiceError(RuntimeError):
    """An error raised while communicating with or parsing OpenAlex."""


class OpenAlexService:
    """Search OpenAlex Works and convert results into LiteratureItem objects."""

    async def search(self, query: str, limit: int) -> list[LiteratureItem]:
        params: dict[str, str | int] = {
            "search": query,
            "per_page": limit,
        }
        api_key = os.getenv("OPENALEX_API_KEY")
        if api_key:
            params["api_key"] = api_key

        try:
            async with httpx.AsyncClient(
                timeout=REQUEST_TIMEOUT,
                headers={"User-Agent": "ai-research-platform/0.2"},
            ) as client:
                response = await client.get(WORKS_URL, params=params)
                _raise_for_openalex_status(response, has_api_key=bool(api_key))
                try:
                    data = response.json()
                    results = data["results"]
                except (ValueError, KeyError, TypeError) as exc:
                    raise OpenAlexServiceError(
                        "OpenAlex returned an invalid response"
                    ) from exc
        except httpx.TimeoutException as exc:
            logger.exception("OpenAlex request timed out")
            raise OpenAlexServiceError("OpenAlex service timed out; please try again") from exc
        except httpx.RequestError as exc:
            logger.exception("OpenAlex network request failed")
            raise OpenAlexServiceError("OpenAlex service is temporarily unavailable") from exc

        if not isinstance(results, list):
            raise OpenAlexServiceError("OpenAlex returned an invalid response")

        items: list[LiteratureItem] = []
        for work in results:
            try:
                item = _parse_openalex_work(work)
            except (AttributeError, TypeError, ValueError):
                logger.exception("Skipping one malformed OpenAlex work")
                continue
            if item is not None:
                items.append(item)
        return items


def _raise_for_openalex_status(response: httpx.Response, has_api_key: bool) -> None:
    try:
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        logger.error("OpenAlex returned HTTP %s", response.status_code)
        if response.status_code == 429:
            raise OpenAlexServiceError(
                "OpenAlex rate limit reached; please try again later"
            ) from exc
        if response.status_code in {401, 403} and not has_api_key:
            raise OpenAlexServiceError(
                "OpenAlex rejected anonymous access; configure OPENALEX_API_KEY"
            ) from exc
        raise OpenAlexServiceError("OpenAlex service is temporarily unavailable") from exc


def _parse_openalex_work(work: Any) -> LiteratureItem | None:
    if not isinstance(work, dict):
        return None

    raw_id = work.get("id")
    if not isinstance(raw_id, str) or not raw_id:
        return None
    openalex_id = raw_id.rstrip("/").rsplit("/", maxsplit=1)[-1]

    authors: list[str] = []
    for authorship in work.get("authorships") or []:
        author = authorship.get("author") if isinstance(authorship, dict) else None
        name = author.get("display_name") if isinstance(author, dict) else None
        if isinstance(name, str) and name.strip():
            authors.append(name.strip())

    publication_year = work.get("publication_year")
    if not isinstance(publication_year, int):
        publication_year = None

    journal = _source_name(work.get("primary_location"))
    if journal is None:
        journal = _source_name(work.get("best_oa_location"))

    doi = _normalise_doi(work.get("doi"))
    publication_date = _optional_string(work.get("publication_date"))
    title = _optional_string(work.get("display_name")) or _optional_string(
        work.get("title")
    )

    return LiteratureItem(
        id=openalex_id,
        source="openalex",
        title=title,
        authors=authors,
        abstract=_reconstruct_abstract(work.get("abstract_inverted_index")),
        publication_date=publication_date,
        year=publication_year,
        journal=journal,
        doi=doi,
        url=raw_id,
    )


def _reconstruct_abstract(inverted_index: Any) -> str | None:
    """Convert OpenAlex's {word: [positions]} structure back into plain text."""

    if not isinstance(inverted_index, dict):
        return None

    positioned_words: list[tuple[int, str]] = []
    for word, positions in inverted_index.items():
        if not isinstance(word, str) or not isinstance(positions, list):
            continue
        for position in positions:
            if isinstance(position, int):
                positioned_words.append((position, word))

    if not positioned_words:
        return None
    positioned_words.sort(key=lambda item: item[0])
    return " ".join(word for _, word in positioned_words)


def _source_name(location: Any) -> str | None:
    if not isinstance(location, dict):
        return None
    source = location.get("source")
    if not isinstance(source, dict):
        return None
    return _optional_string(source.get("display_name"))


def _normalise_doi(value: Any) -> str | None:
    doi = _optional_string(value)
    if doi is None:
        return None
    return re.sub(r"^https?://(?:dx\.)?doi\.org/", "", doi, flags=re.IGNORECASE)


def _optional_string(value: Any) -> str | None:
    return value.strip() if isinstance(value, str) and value.strip() else None
