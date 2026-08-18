"""PubMed ESearch/EFetch integration and XML metadata parsing."""

import logging
import os
import re
import xml.etree.ElementTree as ET

import httpx

from backend.schemas.literature import LiteratureItem


logger = logging.getLogger(__name__)

ESEARCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
EFETCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
REQUEST_TIMEOUT = httpx.Timeout(20.0, connect=8.0)
YEAR_PATTERN = re.compile(r"\b(?:18|19|20|21)\d{2}\b")


class PubMedServiceError(RuntimeError):
    """An error raised while communicating with or parsing PubMed."""


class PubMedService:
    """Search PubMed and convert its XML records into LiteratureItem objects."""

    async def search(self, query: str, limit: int) -> list[LiteratureItem]:
        params = {
            "db": "pubmed",
            "term": query,
            "retmax": limit,
            "retmode": "json",
            "sort": "relevance",
            "tool": "ai_research_platform",
        }
        api_key = os.getenv("NCBI_API_KEY")
        if api_key:
            params["api_key"] = api_key

        try:
            async with httpx.AsyncClient(
                timeout=REQUEST_TIMEOUT,
                headers={"User-Agent": "ai-research-platform/0.2"},
            ) as client:
                search_response = await client.get(ESEARCH_URL, params=params)
                _raise_for_pubmed_status(search_response)
                try:
                    search_data = search_response.json()
                    pmids = search_data["esearchresult"]["idlist"]
                except (ValueError, KeyError, TypeError) as exc:
                    raise PubMedServiceError("PubMed returned an invalid search response") from exc

                if not pmids:
                    return []

                fetch_params = {
                    "db": "pubmed",
                    "id": ",".join(pmids),
                    "retmode": "xml",
                    "tool": "ai_research_platform",
                }
                if api_key:
                    fetch_params["api_key"] = api_key

                fetch_response = await client.get(EFETCH_URL, params=fetch_params)
                _raise_for_pubmed_status(fetch_response)
        except httpx.TimeoutException as exc:
            logger.exception("PubMed request timed out")
            raise PubMedServiceError("PubMed service timed out; please try again") from exc
        except httpx.RequestError as exc:
            logger.exception("PubMed network request failed")
            raise PubMedServiceError("PubMed service is temporarily unavailable") from exc

        return _parse_pubmed_xml(fetch_response.text)


def _raise_for_pubmed_status(response: httpx.Response) -> None:
    try:
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        logger.error("PubMed returned HTTP %s", response.status_code)
        if response.status_code == 429:
            raise PubMedServiceError("PubMed rate limit reached; please try again later") from exc
        raise PubMedServiceError("PubMed service is temporarily unavailable") from exc


def _parse_pubmed_xml(xml_text: str) -> list[LiteratureItem]:
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as exc:
        logger.exception("Unable to parse PubMed XML")
        raise PubMedServiceError("PubMed returned an invalid response") from exc

    items: list[LiteratureItem] = []
    for article in root.findall(".//PubmedArticle"):
        try:
            item = _parse_pubmed_article(article)
        except (AttributeError, TypeError, ValueError):
            logger.exception("Skipping one malformed PubMed article")
            continue
        if item is not None:
            items.append(item)
    return items


def _parse_pubmed_article(article: ET.Element) -> LiteratureItem | None:
    pmid = _text(article.find("./MedlineCitation/PMID"))
    if not pmid:
        return None

    title = _text(article.find("./MedlineCitation/Article/ArticleTitle"))
    authors = _parse_authors(article)
    abstract = _parse_abstract(article)
    publication_date, year = _parse_publication_date(article)
    journal = _text(article.find("./MedlineCitation/Article/Journal/Title"))
    if not journal:
        journal = _text(article.find("./MedlineCitation/MedlineJournalInfo/MedlineTA"))
    doi = _parse_doi(article)

    return LiteratureItem(
        id=pmid,
        source="pubmed",
        title=title,
        authors=authors,
        abstract=abstract,
        publication_date=publication_date,
        year=year,
        journal=journal,
        doi=doi,
        url=f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
    )


def _parse_authors(article: ET.Element) -> list[str]:
    authors: list[str] = []
    for author in article.findall("./MedlineCitation/Article/AuthorList/Author"):
        collective_name = _text(author.find("CollectiveName"))
        if collective_name:
            authors.append(collective_name)
            continue

        first_name = _text(author.find("ForeName")) or _text(author.find("Initials"))
        last_name = _text(author.find("LastName"))
        full_name = " ".join(part for part in (first_name, last_name) if part)
        if full_name:
            authors.append(full_name)
    return authors


def _parse_abstract(article: ET.Element) -> str | None:
    sections: list[str] = []
    for abstract_element in article.findall(
        "./MedlineCitation/Article/Abstract/AbstractText"
    ):
        section_text = _text(abstract_element)
        if not section_text:
            continue
        label = abstract_element.get("Label")
        sections.append(f"{label}: {section_text}" if label else section_text)
    return "\n\n".join(sections) or None


def _parse_publication_date(article: ET.Element) -> tuple[str | None, int | None]:
    date_elements = [
        article.find("./MedlineCitation/Article/ArticleDate"),
        article.find("./MedlineCitation/Article/Journal/JournalIssue/PubDate"),
        article.find("./MedlineCitation/DateCompleted"),
        article.find("./PubmedData/History/PubMedPubDate[@PubStatus='pubmed']"),
    ]

    for date_element in date_elements:
        if date_element is None:
            continue
        medline_date = _text(date_element.find("MedlineDate"))
        if medline_date:
            return medline_date, _extract_year(medline_date)

        parts = [
            _text(date_element.find("Year")),
            _text(date_element.find("Month")),
            _text(date_element.find("Day")),
        ]
        publication_date = "-".join(part for part in parts if part)
        if publication_date:
            return publication_date, _extract_year(publication_date)

    return None, None


def _parse_doi(article: ET.Element) -> str | None:
    for identifier in article.findall("./PubmedData/ArticleIdList/ArticleId"):
        if identifier.get("IdType", "").lower() == "doi":
            return _normalise_doi(_text(identifier))
    for identifier in article.findall("./MedlineCitation/Article/ELocationID"):
        if identifier.get("EIdType", "").lower() == "doi":
            return _normalise_doi(_text(identifier))
    return None


def _normalise_doi(doi: str | None) -> str | None:
    if not doi:
        return None
    return re.sub(r"^https?://(?:dx\.)?doi\.org/", "", doi, flags=re.IGNORECASE)


def _extract_year(value: str) -> int | None:
    match = YEAR_PATTERN.search(value)
    return int(match.group(0)) if match else None


def _text(element: ET.Element | None) -> str | None:
    if element is None:
        return None
    value = " ".join("".join(element.itertext()).split())
    return value or None
