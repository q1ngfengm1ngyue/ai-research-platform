"""Project workspace CRUD endpoints."""

from typing import Annotated
import uuid

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from backend.api.dependencies import get_database_session
from backend.schemas.projects import ProjectCreate, ProjectResponse, ProjectUpdate
from backend.services.project_service import (
    create_project,
    delete_project,
    get_project,
    get_project_with_count,
    list_projects,
    update_project,
)


router = APIRouter(prefix="/projects", tags=["projects"])
DatabaseSession = Annotated[Session, Depends(get_database_session)]


def _project_response(project: object, paper_count: int = 0) -> ProjectResponse:
    return ProjectResponse.model_validate(project).model_copy(
        update={"paper_count": paper_count}
    )


def _database_unavailable(exc: SQLAlchemyError) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="PostgreSQL is unavailable; check DATABASE_URL and database status",
    )


@router.post("", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
def create_project_route(payload: ProjectCreate, session: DatabaseSession) -> ProjectResponse:
    try:
        return _project_response(create_project(session, payload))
    except SQLAlchemyError as exc:
        session.rollback()
        raise _database_unavailable(exc) from exc


@router.get("", response_model=list[ProjectResponse])
def list_projects_route(session: DatabaseSession) -> list[ProjectResponse]:
    try:
        return [_project_response(project, count) for project, count in list_projects(session)]
    except SQLAlchemyError as exc:
        raise _database_unavailable(exc) from exc


@router.get("/{project_id}", response_model=ProjectResponse)
def get_project_route(project_id: uuid.UUID, session: DatabaseSession) -> ProjectResponse:
    try:
        result = get_project_with_count(session, project_id)
    except SQLAlchemyError as exc:
        raise _database_unavailable(exc) from exc
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    return _project_response(*result)


@router.patch("/{project_id}", response_model=ProjectResponse)
def update_project_route(
    project_id: uuid.UUID, payload: ProjectUpdate, session: DatabaseSession
) -> ProjectResponse:
    try:
        project = get_project(session, project_id)
        if project is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Project not found"
            )
        updated = update_project(session, project, payload)
        result = get_project_with_count(session, updated.id)
        assert result is not None
        return _project_response(*result)
    except HTTPException:
        raise
    except SQLAlchemyError as exc:
        session.rollback()
        raise _database_unavailable(exc) from exc


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project_route(project_id: uuid.UUID, session: DatabaseSession) -> Response:
    try:
        project = get_project(session, project_id)
        if project is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Project not found"
            )
        delete_project(session, project)
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except HTTPException:
        raise
    except SQLAlchemyError as exc:
        session.rollback()
        raise _database_unavailable(exc) from exc
