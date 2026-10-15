from sqlalchemy import text
from sqlalchemy.orm import Session

from app.services.embedding_service import model


def semantic_search(
    db: Session,
    repository_id: int,
    query: str,
    limit: int = 5,
) -> list[dict]:
    """Find code chunks using embedding similarity."""

    query_embedding = model.encode(
        query,
        normalize_embeddings=True,
    )

    embedding_string = str(query_embedding.tolist())

    statement = text("""
        SELECT
            cc.id AS chunk_id,
            cc.content,
            cc.start_line,
            cc.end_line,
            cc.chunk_index,
            rf.path,
            rf.language,
            r.id AS repository_id,
            r.name AS repository_name,
            1 - (cc.embedding <=> CAST(:embedding AS vector))
                AS similarity_score
        FROM code_chunks AS cc
        JOIN repository_files AS rf
            ON cc.file_id = rf.id
        JOIN repositories AS r
            ON rf.repository_id = r.id
        WHERE r.id = :repository_id
          AND cc.embedding IS NOT NULL  
        ORDER BY cc.embedding <=> CAST(:embedding AS vector)
        LIMIT :limit
    """)

    results = (
        db.execute(
            statement,
            {
                "embedding": embedding_string,
                "repository_id": repository_id,
                "limit": limit,
            },
        )
        .mappings()
        .all()
    )

    return [dict(row) for row in results]
