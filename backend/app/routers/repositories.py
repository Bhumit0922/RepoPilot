import logging
import httpx

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.exc import SQLAlchemyError

from app.services.repository_ingestion import ingest_repository

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/repositories",
    tags=["RepoPilot"],
)


class IngestRequest(BaseModel):
    repository_url: str = Field(
        min_length=10,
        max_length=2048,
    )


@router.post("/ingest")
def ingest(request: IngestRequest):
    logger.info("Received repository ingestion request: %s", request.repository_url)
    try:
        return ingest_repository(request.repository_url)

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    except httpx.HTTPStatusError as exc:
        raise HTTPException(
            status_code=502,
            detail=(
                "GitHub returned an unsuccessful response. "
                "Check the repository URL, rate limits, and "
                "repository availability."
            ),
        ) from exc

    except httpx.RequestError as exc:
        raise HTTPException(
            status_code=502,
            detail="Could not connect to GitHub. Check your network.",
        ) from exc

    except SQLAlchemyError as exc:
        logger.exception("Database error during repository ingestion")

        raise HTTPException(
            status_code=500,
            detail="A database operation failed during ingestion.",
        ) from exc

    except Exception as exc:
        logger.exception("Unexpected error during repository ingestion")
        raise HTTPException(
            status_code=500,
            detail="An unexpected error occurred during repository ingestion.",
        ) from exc
