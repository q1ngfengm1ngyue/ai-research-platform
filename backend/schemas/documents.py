"""API schemas for retrieved paper documents."""

from datetime import datetime
from typing import Literal
import uuid

from pydantic import BaseModel


class DocumentResponse(BaseModel):
    """Safe document status with a bounded text preview."""

    id: uuid.UUID | None = None
    paper_id: uuid.UUID
    source: str | None = None
    source_url: str | None = None
    content_type: str | None = None
    title: str | None = None
    retrieval_status: Literal[
        "not_retrieved", "available", "unavailable", "failed"
    ]
    text_available: bool = False
    text_length: int = 0
    text_preview: str | None = None
    error_message: str | None = None
    retrieved_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    cached: bool = False
