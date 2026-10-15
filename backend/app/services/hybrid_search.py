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

    # Combine keyword and semantic rankings.
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

            for key, value in result.items():
                if key not in {
                    "keyword_rank",
                    "semantic_rank",
                    "hybrid_score",
                }:
                    if key not in item or item[key] is None:
                        item[key] = value

            item[f"{source}_rank"] = rank

            # Keyword matches receive more weight than semantic matches.
            weight = 1.0 if source == "keyword" else 0.7
            item["hybrid_score"] += weight / (rrf_k + rank)

    query_lower = query.lower()
    identifier_query = re.fullmatch(r"[A-Za-z_]\w*", query)

    for item in combined.values():
        content_lower = item.get("content", "").lower()
        path_lower = item.get("path", "").lower()

        similarity = item.get("similarity_score")

        # Additional code-aware ranking for identifier searches.
        if identifier_query:
            pattern = r"(?<!\w)" + re.escape(query_lower) + r"(?!\w)"

            if re.search(pattern, content_lower):
                item["hybrid_score"] += 0.03

            definition_patterns = [
                rf"\bdef\s+{re.escape(query_lower)}\s*\(",
                rf"\basync\s+def\s+{re.escape(query_lower)}\s*\(",
                rf"\bfunction\s+{re.escape(query_lower)}\s*\(",
                rf"\b{re.escape(query_lower)}\s*=\s*function\b",
                rf"\b{re.escape(query_lower)}\s*=\s*\(",
            ]

            if any(
                re.search(pattern, content_lower) for pattern in definition_patterns
            ):
                item["hybrid_score"] += 0.04

            # Penalize semantic-only results missing the identifier.
            if item["keyword_rank"] is None and not re.search(
                pattern, content_lower + " " + path_lower
            ):
                item["hybrid_score"] *= 0.5

        # Small bonus when the query appears in the file path.
        if query_lower in path_lower:
            item["hybrid_score"] += 0.005

    ranked_results = sorted(
        combined.values(),
        key=lambda item: item["hybrid_score"],
        reverse=True,
    )

    # Keep only the highest-ranked chunk from each file.
    unique_results = []
    seen_paths = set()

    for item in ranked_results:
        path = item.get("path")

        if path in seen_paths:
            continue

        seen_paths.add(path)
        unique_results.append(item)

        if len(unique_results) >= limit:
            break

    return unique_results
