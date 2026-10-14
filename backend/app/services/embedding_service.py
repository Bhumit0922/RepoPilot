from sentence_transformers import SentenceTransformer
from sqlalchemy import text
from sqlalchemy.orm import Session

MODEL_NAME = "all-MiniLM-L6-v2"

model = SentenceTransformer(MODEL_NAME)


def generate_embeddings_for_chunks(
    db: Session,
    chunk_ids: list[int],
    batch_size: int = 32,
) -> int:
    """Generate and save embeddings for the specified chunks."""

    if not chunk_ids:
        return 0

    rows = db.execute(
        text("""
            SELECT id, content
            FROM code_chunks
            WHERE id = ANY(:chunk_ids)
              AND embedding IS NULL
            ORDER BY id
        """),
        {"chunk_ids": chunk_ids},
    ).fetchall()

    total_updated = 0

    for start in range(0, len(rows), batch_size):
        batch = rows[start : start + batch_size]

        vectors = model.encode(
            [row.content for row in batch],
            normalize_embeddings=True,
            show_progress_bar=False,
        )

        for row, vector in zip(batch, vectors):
            db.execute(
                text("""
                    UPDATE code_chunks
                    SET embedding = CAST(:embedding AS vector)
                    WHERE id = :chunk_id
                """),
                {
                    "chunk_id": row.id,
                    "embedding": str(vector.tolist()),
                },
            )

        total_updated += len(batch)

    return total_updated


def generate_embeddings(
    db: Session,
    batch_size: int = 32,
) -> int:
    """Generate embeddings for all chunks that lack them."""

    rows = db.execute(text("""
            SELECT id
            FROM code_chunks
            WHERE embedding IS NULL
            ORDER BY id
        """)).fetchall()

    chunk_ids = [row.id for row in rows]

    total_updated = 0

    for start in range(0, len(chunk_ids), batch_size):
        total_updated += generate_embeddings_for_chunks(
            db,
            chunk_ids[start : start + batch_size],
            batch_size=batch_size,
        )

    return total_updated
