"""FastAPI application entry point for the V1 prototype."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

from backend.api.routes.literature import router as literature_router


load_dotenv()


app = FastAPI(
    title="AI Research Assistant Platform",
    description="V1 prototype backend",
    version="0.2.0",
)

# The frontend is served locally on port 5500 during V1 development.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:5500",
        "http://localhost:5500",
    ],
    allow_credentials=True,
    allow_methods=["GET"],
    allow_headers=["*"],
)

app.include_router(literature_router)


@app.get("/")
async def root() -> dict[str, str]:
    """Return a simple message proving that the API is running."""

    return {"message": "AI Research Platform is running"}


@app.get("/health")
async def health() -> dict[str, str]:
    """Return the current health status of the API."""

    return {"status": "ok"}
