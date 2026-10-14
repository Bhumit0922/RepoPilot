from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Repository
from app.services.code_search import search_code

from app.services.semantic_search import semantic_search

from app.services.hybrid_search import hybrid_search

router = APIRouter(prefix="/search", tags=["Code Search"])


@router.get("/code")
def search_repository_code(
    repository_id: int = Query(gt=0),
    query: str = Query(min_length=1, max_length=200),
    limit: int = Query(default=10, ge=1, le=50),
    db: Session = Depends(get_db),
):
    repository = db.get(Repository, repository_id)

    if repository is None:
        raise HTTPException(
            status_code=404,
            detail="Repository not found.",
        )

    results = search_code(
        db=db,
        repository_id=repository_id,
        query=query,
        limit=limit,
    )

    return {
        "repository_id": repository_id,
        "repository_name": repository.name,
        "query": query,
        "results_count": len(results),
        "results": results,
    }


@router.get("/semantic")
def search_repository_semantic(
    repository_id: int,
    query: str,
    limit: int = 5,
    db: Session = Depends(get_db),
):
    results = semantic_search(
        db=db,
        repository_id=repository_id,
        query=query,
        limit=limit,
    )

    return {
        "repository_id": repository_id,
        "query": query,
        "results_count": len(results),
        "results": results,
    }


@router.get("/hybrid")
def search_repository_hybrid(
    repository_id: int,
    query: str,
    limit: int = 10,
    db: Session = Depends(get_db),
):
    results = hybrid_search(
        db=db,
        repository_id=repository_id,
        query=query,
        limit=limit,
    )

    return {
        "repository_id": repository_id,
        "query": query,
        "results_count": len(results),
        "results": results,
    }
