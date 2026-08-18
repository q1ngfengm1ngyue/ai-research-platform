"""Request and response schemas for projects and saved papers."""

from datetime import datetime
from typing import Literal, Self
import uuid

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=5000)

    @field_validator("name")
    @classmethod
    def strip_name(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Project name cannot be empty")
        return value.strip()


class ProjectUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=5000)

    @field_validator("name")
    @classmethod
    def strip_optional_name(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise ValueError("Project name cannot be empty")
        return value.strip() if value is not None else None

    @model_validator(mode="after")
    def require_change(self) -> Self:
        if "name" not in self.model_fields_set and "description" not in self.model_fields_set:
            raise ValueError("At least one project field must be provided")
        return self


class ProjectResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    description: str | None
    created_at: datetime
    updated_at: datetime
    paper_count: int = 0


class PaperSaveRequest(BaseModel):
    source: Literal["pubmed", "openalex"]
    external_id: str = Field(min_length=1, max_length=200)
    title: str | None = None
    abstract: str | None = None
    authors: list[str] = Field(default_factory=list)
    journal: str | None = Field(default=None, max_length=500)
    publication_year: int | None = Field(default=None, ge=1000, le=3000)
    doi: str | None = Field(default=None, max_length=300)
    url: str | None = None

    @field_validator("external_id")
    @classmethod
    def strip_external_id(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("External id cannot be empty")
        return value.strip()


class PaperResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    source: Literal["pubmed", "openalex"]
    external_id: str
    title: str | None
    abstract: str | None
    authors: list[str]
    journal: str | None
    publication_year: int | None
    doi: str | None
    url: str | None
    created_at: datetime


class PaperSaveResponse(BaseModel):
    created: bool
    paper: PaperResponse
