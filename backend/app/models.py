
from datetime import datetime

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Repository(Base):
    __tablename__ = "repositories"

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    repository_url: Mapped[str] = mapped_column(
        String(1000), nullable=False, unique=True
    )
    default_branch: Mapped[str] = mapped_column(
        String(255), default="main", nullable=False
    )
    status: Mapped[str] = mapped_column(
        String(50), default="pending", nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, index=True
    )
    filename: Mapped[str] = mapped_column(
        String(500), nullable=False
    )
    storage_key: Mapped[str | None] = mapped_column(
        String(1000), nullable=True
    )
    status: Mapped[str] = mapped_column(
        String(50), default="uploaded", nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )


class ProcessingJob(Base):
    __tablename__ = "processing_jobs"

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, index=True
    )
    project: Mapped[str] = mapped_column(
        String(50), nullable=False
    )
    resource_type: Mapped[str] = mapped_column(
        String(50), nullable=False
    )
    resource_id: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )
    status: Mapped[str] = mapped_column(
        String(50), default="pending", nullable=False
    )
    error_message: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

class RepositoryFile(Base):
    __tablename__ = "repository_files"

    __table_args__ = (
        UniqueConstraint(
            "repository_id",
            "path",
            name="uq_repository_file_path",
        ),
    )

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        index=True,
    )

    repository_id: Mapped[int] = mapped_column(
        ForeignKey("repositories.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    path: Mapped[str] = mapped_column(String(1024))
    language: Mapped[str] = mapped_column(String(50))
    sha: Mapped[str] = mapped_column(String(100))
    content: Mapped[str] = mapped_column(Text)
    line_count: Mapped[int] = mapped_column(Integer)


class CodeChunk(Base):
    __tablename__ = "code_chunks"

    __table_args__ = (
        UniqueConstraint(
            "file_id",
            "chunk_index",
            name="uq_code_chunk_position",
        ),
    )

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        index=True,
    )

    file_id: Mapped[int] = mapped_column(
        ForeignKey("repository_files.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    chunk_index: Mapped[int] = mapped_column(Integer)
    start_line: Mapped[int] = mapped_column(Integer)
    end_line: Mapped[int] = mapped_column(Integer)
    content: Mapped[str] = mapped_column(Text)

