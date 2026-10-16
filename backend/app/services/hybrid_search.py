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

    query_lower = query.lower()
    identifier_query = bool(re.fullmatch(r"[A-Za-z_]\w*", query))

    fetch_limit = max(limit * 10, 50)

    keyword_results = search_code(db, repository_id, query, limit=fetch_limit)
    semantic_results = semantic_search(db, repository_id, query, limit=fetch_limit)

    combined = {}
    rrf_k = 60

    # Combine keyword and semantic rankings using reciprocal rank fusion.
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

            # Preserve fields from both search methods.
            for key, value in result.items():
                if key not in {
                    "keyword_rank",
                    "semantic_rank",
                    "hybrid_score",
                }:
                    if key not in item or item[key] is None:
                        item[key] = value

            item[f"{source}_rank"] = rank

            # RRF score.
            item["hybrid_score"] += 1.0 / (rrf_k + rank)

            # Small semantic similarity bonus.
            if source == "semantic":
                similarity = result.get("similarity_score") or 0.0
                item["hybrid_score"] += 0.1 * max(0.0, similarity)

    # Apply code-aware ranking adjustments.
    for item in combined.values():
        content_lower = item.get("content", "").lower()
        path_lower = item.get("path", "").lower()

        if identifier_query:
            pattern = r"(?<!\w)" + re.escape(query_lower) + r"(?!\w)"

            # Reward exact identifier occurrences.
            if re.search(pattern, content_lower):
                item["hybrid_score"] += 0.03

            # Reward likely function definitions.
            definition_patterns = [
                rf"\bdef\s+{re.escape(query_lower)}\s*\(",
                rf"\basync\s+def\s+{re.escape(query_lower)}\s*\(",
                rf"\bfunction\s+{re.escape(query_lower)}\s*\(",
                rf"\b{re.escape(query_lower)}\s*=\s*function\b",
                rf"\b{re.escape(query_lower)}\s*=\s*\(",
            ]

            if any(re.search(p, content_lower) for p in definition_patterns):
                item["hybrid_score"] += 0.04

            # Penalize semantic-only results without the identifier.
            if item["keyword_rank"] is None and not re.search(
                pattern, content_lower + " " + path_lower
            ):
                item["hybrid_score"] *= 0.5

        # Reward a query that appears directly in the file path.
        if query_lower in path_lower:
            item["hybrid_score"] += 0.005

    # Diagnostic output for selected natural-language queries.
    diagnostic_queries = {
        "initialize application",
        "register application routes",
        "load configuration",
    }

    if query_lower in diagnostic_queries:
        print(f"\nCandidate check: {query}")

        expected_path = "examples/tutorial/flaskr/__init__.py"
        matching_items = [
            item for item in combined.values() if item.get("path") == expected_path
        ]

        print(
            "Expected file found in candidates:",
            bool(matching_items),
        )

        for item in matching_items:
            print(
                f"Path: {item.get('path')}",
                f"Keyword rank: {item.get('keyword_rank')}",
                f"Semantic rank: {item.get('semantic_rank')}",
                f"Similarity: {item.get('similarity_score')}",
                f"Score: {item['hybrid_score']:.6f}",
            )

        print("\nTop 10 combined chunks before file deduplication:")

        for item in sorted(
            combined.values(),
            key=lambda x: x["hybrid_score"],
            reverse=True,
        )[:10]:
            print(
                item.get("path"),
                "keyword_rank =",
                item.get("keyword_rank"),
                "semantic_rank =",
                item.get("semantic_rank"),
                "similarity =",
                item.get("similarity_score"),
                "score =",
                round(item["hybrid_score"], 6),
            )

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
