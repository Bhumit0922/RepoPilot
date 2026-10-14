
from app.db import SessionLocal
from app.services.embedding_service import generate_embeddings


def main():
    db = SessionLocal()

    try:
        count = generate_embeddings(db)
        print(f"Embeddings generated and saved: {count}")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
