"""Orchestration from saved Paper metadata to normalized document text."""

from dataclasses import dataclass
import logging
from urllib.parse import urlsplit, urlunsplit

import httpx

from backend.models.project import Paper
from backend.services.documents.http_client import (
    REQUEST_TIMEOUT,
    USER_AGENT,
    RemoteAccessError,
    fetch_bytes,
)
from backend.services.documents.parsers import DocumentParseError, parse_document
from backend.services.documents.sources import (
    FullTextCandidate,
    discover_candidates,
)


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class AcquisitionOutcome:
    source: str
    source_url: str | None
    content_type: str | None
    title: str | None
    text: str | None
    retrieval_status: str
    error_message: str | None


class DocumentAcquisitionService:
    """Fetch and parse ranked candidates without depending on provider details."""

    def __init__(
        self,
        client: httpx.AsyncClient | None = None,
        *,
        validate_hosts: bool = True,
    ) -> None:
        self.client = client
        self.validate_hosts = validate_hosts

    async def acquire(self, paper: Paper) -> AcquisitionOutcome:
        if self.client is not None:
            return await self._acquire_with_client(self.client, paper)
        async with httpx.AsyncClient(
            timeout=REQUEST_TIMEOUT,
            headers={
                "User-Agent": USER_AGENT,
                "Accept": "application/xml,text/html,application/pdf,*/*;q=0.5",
            },
            follow_redirects=False,
        ) as client:
            return await self._acquire_with_client(client, paper)

    async def _acquire_with_client(
        self, client: httpx.AsyncClient, paper: Paper
    ) -> AcquisitionOutcome:
        discovery = await discover_candidates(
            client, paper, validate_hosts=self.validate_hosts
        )
        errors = list(discovery.errors)
        last_candidate: FullTextCandidate | None = None
        for candidate in discovery.candidates:
            last_candidate = candidate
            outcome, error = await self._retrieve_candidate(client, paper, candidate)
            if outcome is not None:
                return outcome
            if error:
                errors.append(error)

        if errors:
            return AcquisitionOutcome(
                source=last_candidate.provider if last_candidate else "unknown",
                source_url=(
                    _public_source_url(last_candidate.public_url or last_candidate.url)
                    if last_candidate
                    else None
                ),
                content_type=None,
                title=paper.title,
                text=None,
                retrieval_status="failed",
                error_message="; ".join(errors),
            )
        return AcquisitionOutcome(
            source="unknown",
            source_url=None,
            content_type=None,
            title=paper.title,
            text=None,
            retrieval_status="unavailable",
            error_message="No open-access full text source found",
        )

    async def _retrieve_candidate(
        self,
        client: httpx.AsyncClient,
        paper: Paper,
        candidate: FullTextCandidate,
    ) -> tuple[AcquisitionOutcome | None, str | None]:
        try:
            payload = await fetch_bytes(
                client,
                candidate.url,
                params=candidate.params,
                validate_hosts=self.validate_hosts,
            )
            content_type, parsed = parse_document(
                payload.body,
                payload.media_type or candidate.content_type_hint or "",
                payload.url,
            )
            return (
                AcquisitionOutcome(
                    source=candidate.provider,
                    source_url=_public_source_url(candidate.public_url or payload.url),
                    content_type=content_type,
                    title=parsed.title or paper.title,
                    text=parsed.text,
                    retrieval_status="available",
                    error_message=None,
                ),
                None,
            )
        except (RemoteAccessError, DocumentParseError) as exc:
            logger.warning(
                "Document candidate %s failed for paper %s: %s",
                candidate.provider,
                paper.id,
                exc,
            )
            return None, f"{candidate.provider} retrieval failed: {exc}"


def _public_source_url(url: str) -> str:
    """Persist a useful source address without query credentials or fragments."""

    parsed = urlsplit(url)
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, "", ""))
