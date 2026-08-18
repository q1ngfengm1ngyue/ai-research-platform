"""Project-scoped saved-paper endpoints."""

from typing import Annotated
import uuid

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from backend.api.dependencies import get_database_session
from backend.schemas.projects import PaperResponse, PaperSaveRequest, PaperSaveResponse
from backend.services.paper_service import delete_paper, get_paper, list_papers, save_paper
from backend.services.project_service import get_project


router = APIRouter(prefix="/projects/{project_id}/papers", tags=["papers"])
DatabaseSession = Annotated[Session, Depends(get_database_session)]


def _database_unavailable() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="PostgreSQL is unavailable; check DATABASE_URL and database status",
    )


@router.post("", response_model=PaperSaveResponse)
def save_paper_route(
    project_id: uuid.UUID,
    payload: PaperSaveRequest,
    response: Response,
    session: DatabaseSession,
) -> PaperSaveResponse:
    try:
        if get_project(session, project_id) is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Project not found"
            )
        paper, created = save_paper(session, project_id, payload)
    except HTTPException:
        raise
    except SQLAlchemyError as exc:
        session.rollback()
        raise _database_unavailable() from exc

    response.status_code = status.HTTP_201_CREATED if created else status.HTTP_200_OK
    return PaperSaveResponse(created=created, paper=PaperResponse.model_validate(paper))


@router.get("", response_model=list[PaperResponse])
def list_papers_route(
    project_id: uuid.UUID, session: DatabaseSession
) -> list[PaperResponse]:
    try:
        if get_project(session, project_id) is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Project not found"
            )
        return [PaperResponse.model_validate(paper) for paper in list_papers(session, project_id)]
    except HTTPException:
        raise
    except SQLAlchemyError as exc:
        raise _database_unavailable() from exc


@router.delete("/{paper_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_paper_route(
    project_id: uuid.UUID, paper_id: uuid.UUID, session: DatabaseSession
) -> Response:
    try:
        if get_project(session, project_id) is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Project not found"
            )
        paper = get_paper(session, project_id, paper_id)
        if paper is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Paper not found in this project"
            )
        delete_paper(session, paper)
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except HTTPException:
        raise
    except SQLAlchemyError as exc:
        session.rollback()
        raise _database_unavailable() from exc
