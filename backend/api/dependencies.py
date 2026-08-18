"""FastAPI dependencies shared by database-backed routes."""

from collections.abc import Generator

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from backend.database import DatabaseConfigurationError, get_db_session


def get_database_session() -> Generator[Session, None, None]:
    """Translate missing database configuration into a clear API response."""

    try:
        yield from get_db_session()
    except DatabaseConfigurationError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc
