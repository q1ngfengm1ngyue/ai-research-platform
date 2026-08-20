"""Provider-independent discovery of legal full-text candidates."""

from dataclasses import dataclass
import os
import re
from typing import Any
from urllib.parse import quote

import httpx

from backend.models.project import Paper
from backend.services.documents.http_client import RemoteAccessError, fetch_json


ELINK_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/elink.fcgi"
PMC_EFETCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
OPENALEX_WORKS_URL = "https://api.openalex.org/works"
OPENALEX_ID_PATTERN = re.compile(r"^W\d+$", re.IGNORECASE)

STRUCTURED_FULLTEXT_PRIORITY = 10
OA_HTML_PRIORITY = 20
OA_PDF_PRIORITY = 30
PLAIN_TEXT_PRIORITY = 40


@dataclass(frozen=True)
class FullTextCandidate:
    """One legally discoverable document URL, independent of Paper metadata source."""

    provider: str
    url: str
    source_kind: str
    priority: int
    content_type_hint: str | None = None
    params: dict[str, str] | None = None
    public_url: str | None = None


@dataclass(frozen=True)
class CandidateDiscovery:
    """Ranked candidates plus safe provider-discovery errors."""

    candidates: tuple[FullTextCandidate, ...]
    errors: tuple[str, ...]


async def discover_candidates(
    client: httpx.AsyncClient, paper: Paper, *, validate_hosts: bool
) -> CandidateDiscovery:
    """Run current full-text providers and return one ranked candidate stream."""

    candidates: list[FullTextCandidate] = []
    errors: list[str] = []
    providers = (
        ("PMC", discover_from_pmc),
        ("OpenAlex", discover_from_openalex),
    )
    for provider_name, discover in providers:
        try:
            candidates.extend(
                await discover(client, paper, validate_hosts=validate_hosts)
            )
        except RemoteAccessError as exc:
            errors.append(f"{provider_name} lookup failed: {exc}")
    return CandidateDiscovery(
        candidates=tuple(_rank_and_deduplicate(candidates)),
        errors=tuple(errors),
    )


async def discover_from_pmc(
    client: httpx.AsyncClient, paper: Paper, *, validate_hosts: bool
) -> list[FullTextCandidate]:
    """Map known PubMed identifiers to PMC JATS candidates."""

    if paper.source != "pubmed" or not paper.external_id.isdigit():
        return []
    params = {
        "dbfrom": "pubmed",
        "db": "pmc",
        "id": paper.external_id,
        "retmode": "json",
        "tool": "ai_research_platform",
    }
    api_key = os.getenv("NCBI_API_KEY")
    if api_key:
        params["api_key"] = api_key
    data = await fetch_json(
        client, ELINK_URL, params=params, validate_hosts=validate_hosts
    )
    pmc_id = _pmc_id_from_elink(data)
    if pmc_id is None:
        return []
    fetch_params = {
        "db": "pmc",
        "id": pmc_id,
        "retmode": "xml",
        "tool": "ai_research_platform",
    }
    if api_key:
        fetch_params["api_key"] = api_key
    return [
        FullTextCandidate(
            provider="pmc",
            url=PMC_EFETCH_URL,
            source_kind="structured_fulltext",
            priority=STRUCTURED_FULLTEXT_PRIORITY,
            content_type_hint="application/xml",
            params=fetch_params,
            public_url=f"https://pmc.ncbi.nlm.nih.gov/articles/PMC{pmc_id}/",
        )
    ]


async def discover_from_openalex(
    client: httpx.AsyncClient, paper: Paper, *, validate_hosts: bool
) -> list[FullTextCandidate]:
    """Convert OpenAlex-declared OA locations into unified candidates."""

    identifier: str | None = None
    if paper.source == "openalex" and OPENALEX_ID_PATTERN.fullmatch(paper.external_id):
        identifier = paper.external_id.upper()
    elif paper.doi:
        identifier = f"https://doi.org/{paper.doi}"
    if identifier is None:
        return []

    work_url = f"{OPENALEX_WORKS_URL}/{quote(identifier, safe=':/')}"
    params: dict[str, str] = {}
    api_key = os.getenv("OPENALEX_API_KEY")
    if api_key:
        params["api_key"] = api_key
    data = await fetch_json(
        client,
        work_url,
        params=params or None,
        validate_hosts=validate_hosts,
    )
    return _openalex_oa_candidates(data)


def _rank_and_deduplicate(
    candidates: list[FullTextCandidate],
) -> list[FullTextCandidate]:
    """Prefer candidate quality while fetching any duplicated URL only once."""

    by_url: dict[str, FullTextCandidate] = {}
    for candidate in candidates:
        existing = by_url.get(candidate.url)
        if existing is None or candidate.priority < existing.priority:
            by_url[candidate.url] = candidate
    return sorted(by_url.values(), key=lambda candidate: candidate.priority)


def _pmc_id_from_elink(data: Any) -> str | None:
    if not isinstance(data, dict):
        return None
    for linkset in data.get("linksets") or []:
        if not isinstance(linkset, dict):
            continue
        for database_links in linkset.get("linksetdbs") or []:
            if (
                not isinstance(database_links, dict)
                or database_links.get("dbto") != "pmc"
            ):
                continue
            for value in database_links.get("links") or []:
                text = str(value).removeprefix("PMC")
                if text.isdigit():
                    return text
    return None


def _openalex_oa_candidates(data: Any) -> list[FullTextCandidate]:
    if not isinstance(data, dict):
        return []
    open_access = data.get("open_access")
    if not isinstance(open_access, dict) or open_access.get("is_oa") is not True:
        return []

    candidates: list[FullTextCandidate] = []
    locations = [data.get("best_oa_location"), data.get("primary_location")]
    for index, location in enumerate(locations):
        if not isinstance(location, dict):
            continue
        if index > 0 and location.get("is_oa") is not True:
            continue
        landing_page_url = _optional_string(location.get("landing_page_url"))
        if landing_page_url:
            candidates.append(
                FullTextCandidate(
                    provider="openalex",
                    url=landing_page_url,
                    source_kind="oa_html",
                    priority=OA_HTML_PRIORITY,
                    content_type_hint="text/html",
                )
            )
        pdf_url = _optional_string(location.get("pdf_url"))
        if pdf_url:
            candidates.append(
                FullTextCandidate(
                    provider="openalex",
                    url=pdf_url,
                    source_kind="oa_pdf",
                    priority=OA_PDF_PRIORITY,
                    content_type_hint="application/pdf",
                )
            )
    return candidates


def _optional_string(value: Any) -> str | None:
    return value.strip() if isinstance(value, str) and value.strip() else None
