"""Project workspace and saved-paper persistence models."""

from datetime import datetime
import uuid

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from backend.database import Base


class Project(Base):
    """A single-user research workspace."""

    __tablename__ = "projects"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    papers: Mapped[list["Paper"]] = relationship(
        back_populates="project", cascade="all, delete-orphan", passive_deletes=True
    )


class Paper(Base):
    """Provider-independent literature metadata saved inside one project."""

    __tablename__ = "papers"
    __table_args__ = (
        CheckConstraint(
            "source IN ('pubmed', 'openalex')", name="ck_papers_supported_source"
        ),
        UniqueConstraint(
            "project_id",
            "source",
            "external_id",
            name="uq_papers_project_source_external_id",
        ),
        UniqueConstraint(
            "project_id", "doi", name="uq_papers_project_doi"
        ),
        Index("ix_papers_project_id", "project_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    source: Mapped[str] = mapped_column(String(20), nullable=False)
    external_id: Mapped[str] = mapped_column(String(200), nullable=False)
    title: Mapped[str | None] = mapped_column(Text, nullable=True)
    abstract: Mapped[str | None] = mapped_column(Text, nullable=True)
    authors: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    journal: Mapped[str | None] = mapped_column(String(500), nullable=True)
    publication_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    doi: Mapped[str | None] = mapped_column(String(300), nullable=True)
    url: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    project: Mapped[Project] = relationship(back_populates="papers")
