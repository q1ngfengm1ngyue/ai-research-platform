"""Discovery of legal open-access full-text sources."""

from dataclasses import dataclass
import os
import re
from typing import Any
from urllib.parse import quote

import httpx

from backend.models.project import Paper
from backend.services.documents.http_client import fetch_json


ELINK_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/elink.fcgi"
PMC_EFETCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
OPENALEX_WORKS_URL = "https://api.openalex.org/works"
OPENALEX_ID_PATTERN = re.compile(r"^W\d+$", re.IGNORECASE)


@dataclass(frozen=True)
class SourceCandidate:
    source: str
    url: str
    params: dict[str, str] | None = None
    public_url: str | None = None


async def discover_pmc_source(
    client: httpx.AsyncClient, paper: Paper, *, validate_hosts: bool
) -> SourceCandidate | None:
    """Map a PubMed PMID to PMC and return the JATS EFetch endpoint."""

    if paper.source != "pubmed" or not paper.external_id.isdigit():
        return None
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
        return None
    fetch_params = {
        "db": "pmc",
        "id": pmc_id,
        "retmode": "xml",
        "tool": "ai_research_platform",
    }
    if api_key:
        fetch_params["api_key"] = api_key
    return SourceCandidate(
        source="pmc",
        url=PMC_EFETCH_URL,
        params=fetch_params,
        public_url=f"https://pmc.ncbi.nlm.nih.gov/articles/PMC{pmc_id}/",
    )


async def discover_openalex_source(
    client: httpx.AsyncClient, paper: Paper, *, validate_hosts: bool
) -> SourceCandidate | None:
    """Read OpenAlex work metadata and select a declared OA location."""

    identifier: str | None = None
    if paper.source == "openalex" and OPENALEX_ID_PATTERN.fullmatch(paper.external_id):
        identifier = paper.external_id.upper()
    elif paper.doi:
        identifier = f"https://doi.org/{paper.doi}"
    if identifier is None:
        return None

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
    oa_url = _openalex_oa_url(data)
    return SourceCandidate(source="openalex", url=oa_url) if oa_url else None


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


def _openalex_oa_url(data: Any) -> str | None:
    if not isinstance(data, dict):
        return None
    open_access = data.get("open_access")
    if not isinstance(open_access, dict) or open_access.get("is_oa") is not True:
        return None

    locations = [data.get("best_oa_location"), data.get("primary_location")]
    for index, location in enumerate(locations):
        if not isinstance(location, dict):
            continue
        if index > 0 and location.get("is_oa") is not True:
            continue
        for field in ("pdf_url", "landing_page_url"):
            value = location.get(field)
            if isinstance(value, str) and value.strip():
                return value.strip()
    return None
