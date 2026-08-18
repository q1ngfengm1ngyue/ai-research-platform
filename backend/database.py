"""Environment-backed SQLAlchemy database layer."""

from collections.abc import Generator
from functools import lru_cache
import os

from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


load_dotenv()


class DatabaseConfigurationError(RuntimeError):
    """Raised when the PostgreSQL connection is not configured."""


class Base(DeclarativeBase):
    """Declarative base shared by all application models."""


def _database_url() -> str:
    database_url = os.getenv("DATABASE_URL", "").strip()
    if not database_url:
        raise DatabaseConfigurationError(
            "DATABASE_URL is not configured; copy .env.example to .env and set it"
        )
    if not database_url.startswith(("postgresql://", "postgresql+psycopg://")):
        raise DatabaseConfigurationError("DATABASE_URL must point to PostgreSQL")
    return database_url


@lru_cache
def get_engine() -> Engine:
    """Create one lazy PostgreSQL engine for the process."""

    return create_engine(_database_url(), pool_pre_ping=True)


@lru_cache
def get_session_factory() -> sessionmaker[Session]:
    """Return the shared request-session factory."""

    return sessionmaker(
        bind=get_engine(), autoflush=False, expire_on_commit=False, class_=Session
    )


def get_db_session() -> Generator[Session, None, None]:
    """Yield one database session and always close it after the request."""

    session = get_session_factory()()
    try:
        yield session
    finally:
        session.close()


def initialize_database() -> None:
    """Create the V1 tables in an existing PostgreSQL database."""

    from backend import models  # noqa: F401

    Base.metadata.create_all(bind=get_engine())


def check_database_connection() -> None:
    """Run a minimal query to verify the configured connection."""

    with get_engine().connect() as connection:
        connection.execute(text("SELECT 1"))
