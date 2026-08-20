"""SQLAlchemy persistence models."""

from backend.models.document import PaperDocument
from backend.models.project import Paper, Project

__all__ = ["Paper", "PaperDocument", "Project"]
