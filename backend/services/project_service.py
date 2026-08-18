"""Project CRUD business operations."""

import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.models.project import Paper, Project
from backend.schemas.projects import ProjectCreate, ProjectUpdate


def create_project(session: Session, payload: ProjectCreate) -> Project:
    project = Project(name=payload.name, description=payload.description)
    session.add(project)
    session.commit()
    session.refresh(project)
    return project


def list_projects(session: Session) -> list[tuple[Project, int]]:
    statement = (
        select(Project, func.count(Paper.id).label("paper_count"))
        .outerjoin(Paper, Paper.project_id == Project.id)
        .group_by(Project.id)
        .order_by(Project.created_at.desc())
    )
    return [(project, int(count)) for project, count in session.execute(statement)]


def get_project(session: Session, project_id: uuid.UUID) -> Project | None:
    return session.get(Project, project_id)


def get_project_with_count(
    session: Session, project_id: uuid.UUID
) -> tuple[Project, int] | None:
    statement = (
        select(Project, func.count(Paper.id).label("paper_count"))
        .outerjoin(Paper, Paper.project_id == Project.id)
        .where(Project.id == project_id)
        .group_by(Project.id)
    )
    row = session.execute(statement).one_or_none()
    return (row[0], int(row[1])) if row is not None else None


def update_project(
    session: Session, project: Project, payload: ProjectUpdate
) -> Project:
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(project, field, value)
    session.commit()
    session.refresh(project)
    return project


def delete_project(session: Session, project: Project) -> None:
    session.delete(project)
    session.commit()
