"""Provider-independent orchestration for literature searches."""

import asyncio
import logging
from typing import Literal

from backend.schemas.literature import LiteratureItem
from backend.services.literature.openalex_service import OpenAlexService
from backend.services.literature.pubmed_service import PubMedService


logger = logging.getLogger(__name__)


class LiteratureServiceError(RuntimeError):
    """A safe, user-facing error raised by a literature provider."""


async def search_literature(
    query: str,
    source: Literal["pubmed", "openalex", "all"],
    limit: int,
) -> tuple[list[LiteratureItem], list[str]]:
    """Search the requested provider and return unified literature items."""

    if source == "pubmed":
        try:
            return await PubMedService().search(query, limit), []
        except RuntimeError as exc:
            raise LiteratureServiceError(str(exc)) from exc

    if source == "openalex":
        try:
            return await OpenAlexService().search(query, limit), []
        except RuntimeError as exc:
            raise LiteratureServiceError(str(exc)) from exc

    provider_calls = [
        ("PubMed", PubMedService().search(query, limit)),
        ("OpenAlex", OpenAlexService().search(query, limit)),
    ]
    provider_results = await asyncio.gather(
        *(call for _, call in provider_calls),
        return_exceptions=True,
    )

    items: list[LiteratureItem] = []
    warnings: list[str] = []
    failed_providers = 0

    for (provider_name, _), result in zip(provider_calls, provider_results, strict=True):
        if isinstance(result, BaseException):
            failed_providers += 1
            logger.error("%s search failed: %s", provider_name, result)
            warnings.append(f"{provider_name} search is temporarily unavailable")
            continue
        items.extend(result)

    if failed_providers == len(provider_calls):
        raise LiteratureServiceError("Literature services are temporarily unavailable")

    return items, warnings
