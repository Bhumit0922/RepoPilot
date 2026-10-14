import re

from sqlalchemy import case, func, or_, select
from sqlalchemy.orm import Session

from app.models import CodeChunk, RepositoryFile, Repository

SOURCE_LANGUAGES = {
    "python",
    "javascript",
    "typescript",
    "tsx",
    "java",
    "c",
    "cpp",
    "go",
    "rust",
    "ruby",
    "php",
}


def search_code(
    db: Session,
    repository_id: int,
    query: str,
    limit: int = 10,
) -> list[dict]:
    """Search code chunks using keyword and full-text ranking."""

    query = query.strip()

    if not query:
        return []

    pattern = f"%{query}%"
    lower_query = query.lower()

    # Count case-insensitive keyword occurrences.
    occurrence_count = (
        func.length(func.lower(CodeChunk.content))
        - func.length(
            func.replace(
                func.lower(CodeChunk.content),
                lower_query,
                "",
            )
        )
    ) / max(len(lower_query), 1)

    # Reward direct keyword matches.
    exact_match_score = case(
        (func.lower(CodeChunk.content).contains(lower_query), 5),
        else_=0,
    )

    # Prefer supported source-code files.
    source_score = case(
        (RepositoryFile.language.in_(SOURCE_LANGUAGES), 2),
        else_=0,
    )

    # Reward matches in the file path.
    path_score = case(
        (func.lower(RepositoryFile.path).contains(lower_query), 8),
        else_=0,
    )

    # Reward complete identifier matches.
    identifier_pattern = rf"(?<!\w){re.escape(query)}(?!\w)"

    identifier_score = case(
        (
            func.lower(CodeChunk.content).op("~*")(identifier_pattern),
            6,
        ),
        else_=0,
    )

    # Reward function definitions and calls.
    definition_score = case(
        (
            func.lower(CodeChunk.content).contains(f"def {lower_query}"),
            8,
        ),
        else_=0,
    )

    call_score = case(
        (
            func.lower(CodeChunk.content).contains(f"{lower_query}("),
            5,
        ),
        else_=0,
    )

    # PostgreSQL full-text search ranking.
    search_vector = func.to_tsvector(
        "english",
        CodeChunk.content,
    )

    search_query = func.websearch_to_tsquery(
        "english",
        query,
    )

    full_text_score = func.ts_rank_cd(search_vector, search_query) * 10

    total_score = (
        exact_match_score
        + source_score
        + path_score
        + identifier_score
        + definition_score
        + call_score
        + func.least(occurrence_count, 10)
        + full_text_score
    )

    statement = (
        select(
            CodeChunk.id.label("chunk_id"),
            CodeChunk.content,
            CodeChunk.start_line,
            CodeChunk.end_line,
            CodeChunk.chunk_index,
            RepositoryFile.path,
            RepositoryFile.language,
            Repository.id.label("repository_id"),
            Repository.name.label("repository_name"),
            total_score.label("relevance_score"),
        )
        .join(
            RepositoryFile,
            CodeChunk.file_id == RepositoryFile.id,
        )
        .join(
            Repository,
            RepositoryFile.repository_id == Repository.id,
        )
        .where(
            Repository.id == repository_id,
            or_(
                CodeChunk.content.ilike(pattern),
                RepositoryFile.path.ilike(pattern),
                func.to_tsvector("english", CodeChunk.content).op("@@")(
                    func.websearch_to_tsquery("english", query)
                ),
            ),
        )
        .order_by(
            total_score.desc(),
            RepositoryFile.path,
            CodeChunk.chunk_index,
        )
        .limit(limit)
    )

    results = db.execute(statement).mappings().all()

    return [dict(row) for row in results]
