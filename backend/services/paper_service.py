"""Saved-paper persistence and project-scoped deduplication."""

import re
import uuid

from sqlalchemy import and_, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.models.project import Paper
from backend.schemas.projects import PaperSaveRequest


DOI_PREFIX = re.compile(r"^https?://(?:dx\.)?doi\.org/", re.IGNORECASE)


def normalize_doi(doi: str | None) -> str | None:
    if not doi or not doi.strip():
        return None
    return DOI_PREFIX.sub("", doi.strip()).lower()


def save_paper(
    session: Session, project_id: uuid.UUID, payload: PaperSaveRequest
) -> tuple[Paper, bool]:
    normalized_doi = normalize_doi(payload.doi)
    existing = _find_duplicate(
        session,
        project_id,
        payload.source,
        payload.external_id,
        normalized_doi,
    )
    if existing is not None:
        return existing, False

    paper = Paper(
        project_id=project_id,
        source=payload.source,
        external_id=payload.external_id,
        title=payload.title.strip() if payload.title else None,
        abstract=payload.abstract,
        authors=[author.strip() for author in payload.authors if author.strip()],
        journal=payload.journal,
        publication_year=payload.publication_year,
        doi=normalized_doi,
        url=payload.url,
    )
    session.add(paper)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        existing = _find_duplicate(
            session,
            project_id,
            payload.source,
            payload.external_id,
            normalized_doi,
        )
        if existing is None:
            raise
        return existing, False
    session.refresh(paper)
    return paper, True


def list_papers(session: Session, project_id: uuid.UUID) -> list[Paper]:
    statement = (
        select(Paper)
        .where(Paper.project_id == project_id)
        .order_by(Paper.created_at.desc())
    )
    return list(session.scalars(statement))


def get_paper(
    session: Session, project_id: uuid.UUID, paper_id: uuid.UUID
) -> Paper | None:
    return session.scalar(
        select(Paper).where(
            Paper.id == paper_id,
            Paper.project_id == project_id,
        )
    )


def delete_paper(session: Session, paper: Paper) -> None:
    session.delete(paper)
    session.commit()


def _find_duplicate(
    session: Session,
    project_id: uuid.UUID,
    source: str,
    external_id: str,
    doi: str | None,
) -> Paper | None:
    identities = [and_(Paper.source == source, Paper.external_id == external_id)]
    if doi is not None:
        identities.append(Paper.doi == doi)
    return session.scalar(
        select(Paper).where(
            Paper.project_id == project_id,
            or_(*identities),
        )
    )
