"""FastAPI application entry point for the V1 prototype."""

from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from sqlalchemy.exc import SQLAlchemyError

from backend.api.routes.documents import router as documents_router
from backend.api.routes.literature import router as literature_router
from backend.api.routes.papers import router as papers_router
from backend.api.routes.projects import router as projects_router
from backend.database import DatabaseConfigurationError, check_database_connection


load_dotenv()


app = FastAPI(
    title="AI Research Assistant Platform",
    description="V1 prototype backend",
    version="0.5.0",
)

# The frontend is served locally on port 5500 during V1 development.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:3000",
        "http://localhost:3000",
        "http://127.0.0.1:5500",
        "http://localhost:5500",
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["*"],
)

app.include_router(literature_router)
app.include_router(projects_router)
app.include_router(papers_router)
app.include_router(documents_router)


@app.get("/")
async def root() -> dict[str, str]:
    """Return a simple message proving that the API is running."""

    return {"message": "AI Research Platform is running"}


@app.get("/health")
async def health() -> dict[str, str]:
    """Return the current health status of the API."""

    return {"status": "ok"}


@app.get("/health/database")
def database_health() -> dict[str, str]:
    """Verify that the configured PostgreSQL server accepts a query."""

    try:
        check_database_connection()
    except (DatabaseConfigurationError, SQLAlchemyError) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    return {"status": "ok", "database": "postgresql"}
