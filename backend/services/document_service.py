"""Document retrieval caching, persistence, and API presentation."""

from datetime import datetime, timezone
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.models.document import PaperDocument
from backend.models.project import Paper
from backend.schemas.documents import DocumentResponse
from backend.services.documents.acquisition import (
    AcquisitionOutcome,
    DocumentAcquisitionService,
)


TEXT_PREVIEW_LENGTH = 1500


def get_document(session: Session, paper_id: uuid.UUID) -> PaperDocument | None:
    return session.scalar(select(PaperDocument).where(PaperDocument.paper_id == paper_id))


async def get_document_for_paper(
    session: Session,
    paper: Paper,
    *,
    force_refresh: bool = False,
    acquisition_service: DocumentAcquisitionService | None = None,
) -> tuple[PaperDocument, bool]:
    """Return a cached success or acquire and upsert the latest retrieval result."""

    existing = get_document(session, paper.id)
    if existing is not None and existing.retrieval_status == "available" and not force_refresh:
        return existing, True

    service = acquisition_service or DocumentAcquisitionService()
    outcome = await service.acquire(paper)
    document = _apply_outcome(existing or PaperDocument(paper_id=paper.id), outcome)
    session.add(document)
    session.commit()
    session.refresh(document)
    return document, False


def document_response(
    paper_id: uuid.UUID,
    document: PaperDocument | None,
    *,
    cached: bool = False,
) -> DocumentResponse:
    if document is None:
        return DocumentResponse(paper_id=paper_id, retrieval_status="not_retrieved")
    text = document.text or ""
    return DocumentResponse(
        id=document.id,
        paper_id=document.paper_id,
        source=document.source,
        source_url=document.source_url,
        content_type=document.content_type,
        title=document.title,
        retrieval_status=document.retrieval_status,
        text_available=bool(text),
        text_length=len(text),
        text_preview=text[:TEXT_PREVIEW_LENGTH] or None,
        error_message=document.error_message,
        retrieved_at=document.retrieved_at,
        created_at=document.created_at,
        updated_at=document.updated_at,
        cached=cached,
    )


def _apply_outcome(
    document: PaperDocument, outcome: AcquisitionOutcome
) -> PaperDocument:
    document.source = outcome.source
    document.source_url = outcome.source_url
    document.content_type = outcome.content_type
    document.title = outcome.title
    document.text = outcome.text
    document.retrieval_status = outcome.retrieval_status
    document.error_message = outcome.error_message
    document.retrieved_at = datetime.now(timezone.utc)
    return document
