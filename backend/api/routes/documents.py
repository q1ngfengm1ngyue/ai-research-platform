"""Project-scoped document retrieval endpoints."""

from typing import Annotated
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from backend.api.dependencies import get_database_session
from backend.models.project import Paper
from backend.schemas.documents import DocumentResponse
from backend.services.document_service import (
    document_response,
    get_document,
    get_document_for_paper,
)
from backend.services.paper_service import get_paper


router = APIRouter(prefix="/projects/{project_id}/papers", tags=["documents"])
DatabaseSession = Annotated[Session, Depends(get_database_session)]


def _paper_or_404(
    session: Session, project_id: uuid.UUID, paper_id: uuid.UUID
) -> Paper:
    paper = get_paper(session, project_id, paper_id)
    if paper is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Paper not found in this project",
        )
    return paper


def _database_unavailable() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="PostgreSQL is unavailable; check DATABASE_URL and database status",
    )


@router.get("/{paper_id}/document", response_model=DocumentResponse)
def get_document_route(
    project_id: uuid.UUID, paper_id: uuid.UUID, session: DatabaseSession
) -> DocumentResponse:
    """Read the latest persisted retrieval status without making a network request."""

    try:
        paper = _paper_or_404(session, project_id, paper_id)
        return document_response(paper.id, get_document(session, paper.id))
    except HTTPException:
        raise
    except SQLAlchemyError as exc:
        raise _database_unavailable() from exc


@router.post("/{paper_id}/document", response_model=DocumentResponse)
async def retrieve_document_route(
    project_id: uuid.UUID,
    paper_id: uuid.UUID,
    session: DatabaseSession,
    force_refresh: Annotated[bool, Query()] = False,
) -> DocumentResponse:
    """Acquire legal OA text, persist its status, and reuse successful results."""

    try:
        paper = _paper_or_404(session, project_id, paper_id)
        document, cached = await get_document_for_paper(
            session, paper, force_refresh=force_refresh
        )
        return document_response(paper.id, document, cached=cached)
    except HTTPException:
        raise
    except SQLAlchemyError as exc:
        session.rollback()
        raise _database_unavailable() from exc
