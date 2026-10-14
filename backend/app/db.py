
from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import settings


def normalize_database_url(url: str) -> str:
    # Use Psycopg 3 explicitly with SQLAlchemy.
    if url.startswith("postgres://"):
        return url.replace(
            "postgres://",
            "postgresql+psycopg://",
            1,
        )

    if url.startswith("postgresql://"):
        return url.replace(
            "postgresql://",
            "postgresql+psycopg://",
            1,
        )

    return url


DATABASE_URL = normalize_database_url(settings.DATABASE_URL)

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
)

SessionLocal = sessionmaker(
    bind=engine,
    class_=Session,
    autoflush=False,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    pass


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()

    try:
        yield db
    finally:
        db.close()
