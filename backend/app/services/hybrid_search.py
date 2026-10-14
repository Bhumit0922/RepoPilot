import re

from sqlalchemy.orm import Session

from app.services.code_search import search_code
from app.services.semantic_search import semantic_search


def hybrid_search(
    db: Session,
    repository_id: int,
    query: str,
    limit: int = 10,
) -> list[dict]:
    """Combine keyword and semantic search with code-aware ranking."""

    query = query.strip()

    if not query or limit <= 0:
        return []

    fetch_limit = max(limit * 3, 20)

    keyword_results = search_code(db, repository_id, query, limit=fetch_limit)
    semantic_results = semantic_search(db, repository_id, query, limit=fetch_limit)

    combined = {}
    rrf_k = 60

    # Combine rankings using Reciprocal Rank Fusion.
    for source, results in (
        ("keyword", keyword_results),
        ("semantic", semantic_results),
    ):
        for rank, result in enumerate(results, start=1):
            chunk_id = result["chunk_id"]

            if chunk_id not in combined:
                combined[chunk_id] = {
                    **result,
                    "keyword_rank": None,
                    "semantic_rank": None,
                    "hybrid_score": 0.0,
                }

            item = combined[chunk_id]

            # Keep the keyword result's relevance score and the
            # semantic result's similarity score when available.
            for key, value in result.items():
                if key not in {
                    "keyword_rank",
                    "semantic_rank",
                    "hybrid_score",
                }:
                    if key not in item or item[key] is None:
                        item[key] = value

            item[f"{source}_rank"] = rank
            item["hybrid_score"] += 1.0 / (rrf_k + rank)

    query_lower = query.lower()
    identifier_query = re.fullmatch(r"[A-Za-z_]\w*", query)

    # Add code-specific relevance signals.
    for item in combined.values():
        content = item.get("content", "")
        content_lower = content.lower()
        path_lower = item.get("path", "").lower()

        if identifier_query:
            # Match a complete identifier, not a partial word.
            pattern = r"(?<!\w)" + re.escape(query_lower) + r"(?!\w)"

            if re.search(pattern, content_lower):
                item["hybrid_score"] += 0.03

            # Prefer an actual function definition.
            definition_patterns = [
                rf"\bdef\s+{re.escape(query_lower)}\s*\(",
                rf"\bfunction\s+{re.escape(query_lower)}\s*\(",
                rf"\b{re.escape(query_lower)}\s*=\s*function\b",
                rf"\b{re.escape(query_lower)}\s*=\s*\(",
            ]

            if any(
                re.search(pattern, content_lower) for pattern in definition_patterns
            ):
                item["hybrid_score"] += 0.04

        # A matching file path is useful, but weaker than a code match.
        if query_lower in path_lower:
            item["hybrid_score"] += 0.005

        # Down-rank semantic-only results for exact identifier queries
        # when the identifier is absent from their content and path.
        if (
            identifier_query
            and item["keyword_rank"] is None
            and not re.search(
                r"(?<!\w)" + re.escape(query_lower) + r"(?!\w)",
                content_lower + " " + path_lower,
            )
        ):
            item["hybrid_score"] *= 0.8

    return sorted(
        combined.values(),
        key=lambda item: item["hybrid_score"],
        reverse=True,
    )[:limit]
