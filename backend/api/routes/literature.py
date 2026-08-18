"""HTTP routes for literature search."""

from typing import Annotated, Literal

from fastapi import APIRouter, HTTPException, Query, status

from backend.schemas.literature import LiteratureSearchResponse
from backend.services.literature.literature_service import (
    LiteratureServiceError,
    search_literature,
)


router = APIRouter(prefix="/api/literature", tags=["literature"])


@router.get("/search", response_model=LiteratureSearchResponse)
async def search_literature_route(
    q: Annotated[str, Query(min_length=1, max_length=500)],
    source: Literal["pubmed", "openalex", "all"] = "all",
    limit: Annotated[int, Query(ge=1, le=20)] = 10,
) -> LiteratureSearchResponse:
    """Search one or both supported academic literature databases."""

    query = q.strip()
    if not query:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Search query cannot be empty",
        )

    try:
        items, warnings = await search_literature(query, source, limit)
    except LiteratureServiceError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc

    return LiteratureSearchResponse(
        query=query,
        source=source,
        count=len(items),
        results=items,
        warnings=warnings,
    )
