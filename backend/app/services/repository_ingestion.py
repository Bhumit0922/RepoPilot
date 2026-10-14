import logging

from sqlalchemy import delete, select

from app.db import SessionLocal
from app.models import CodeChunk, Repository, RepositoryFile
from app.services.chunking import chunk_source
from app.services.github_client import fetch_repository
from app.services.embedding_service import generate_embeddings_for_chunks

logger = logging.getLogger(__name__)


def ingest_repository(repository_url: str) -> dict:
    # Fetch source files before opening a DB transaction.
    logger.info("Starting GitHub fetch for %s", repository_url)

    canonical_url, branch, source_files = fetch_repository(repository_url)

    logger.info(
        "Fetched %d files for %s on branch %s",
        len(source_files),
        canonical_url,
        branch,
    )

    with SessionLocal() as db:
        try:
            logger.info("Starting database indexing for %s", canonical_url)

            repository = db.scalar(
                select(Repository).where(Repository.repository_url == canonical_url)
            )

            if repository is None:
                repository = Repository(
                    name=canonical_url.rstrip("/").split("/")[-1],
                    repository_url=canonical_url,
                    default_branch=branch,
                    status="indexing",
                )
                db.add(repository)
                db.flush()
            else:
                repository.default_branch = branch
                repository.status = "indexing"

            # Remove the previous index.
            old_file_ids = db.scalars(
                select(RepositoryFile.id).where(
                    RepositoryFile.repository_id == repository.id
                )
            ).all()

            if old_file_ids:
                db.execute(delete(CodeChunk).where(CodeChunk.file_id.in_(old_file_ids)))

            db.execute(
                delete(RepositoryFile).where(
                    RepositoryFile.repository_id == repository.id
                )
            )

            file_count = 0
            chunk_count = 0
            new_chunk_ids = []

            # Create files and code chunks.
            for source_file in source_files:
                file_chunks = chunk_source(
                    source_file.content,
                    source_file.language,
                )

                file_record = RepositoryFile(
                    repository_id=repository.id,
                    path=source_file.path,
                    language=source_file.language,
                    sha=source_file.sha,
                    content=source_file.content,
                    line_count=len(source_file.content.splitlines()),
                )

                db.add(file_record)
                db.flush()

                for chunk_data in file_chunks:
                    chunk = CodeChunk(
                        file_id=file_record.id,
                        **chunk_data,
                    )

                    db.add(chunk)
                    db.flush()

                    new_chunk_ids.append(chunk.id)

                file_count += 1
                chunk_count += len(file_chunks)

            # Generate embeddings for the newly created chunks.
            embedded_count = generate_embeddings_for_chunks(
                db,
                new_chunk_ids,
            )

            logger.info(
                "Generated embeddings for %d chunks in %s",
                embedded_count,
                canonical_url,
            )

            repository.status = "indexed"

            logger.info(
                "Committing %d files and %d chunks for %s",
                file_count,
                chunk_count,
                canonical_url,
            )

            db.commit()

            logger.info(
                "Database indexing complete for %s",
                canonical_url,
            )

            return {
                "repository_id": repository.id,
                "repository_url": canonical_url,
                "default_branch": branch,
                "status": repository.status,
                "files_indexed": file_count,
                "chunks_created": chunk_count,
                "embeddings_generated": embedded_count,
            }

        except Exception:
            logger.exception(
                "Repository indexing failed for %s",
                canonical_url,
            )
            db.rollback()
            raise
