import json
import sys
from pathlib import Path

# Allow imports from the backend directory.
BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from app.db import SessionLocal
from app.services.hybrid_search import hybrid_search

from app.services.code_search import search_code
from app.services.semantic_search import semantic_search

REPOSITORY_ID = 24
LIMIT = 5

DATASET_PATH = Path(__file__).parent / "search_queries.json"


def diagnose_query(db, query, repository_id=24, limit=5):
    print(f"\n{'=' * 60}")
    print(f"DIAGNOSTIC QUERY: {query}")
    print("=" * 60)

    keyword_results = search_code(
        db=db,
        repository_id=repository_id,
        query=query,
        limit=limit,
    )

    semantic_results = semantic_search(
        db=db,
        repository_id=repository_id,
        query=query,
        limit=limit,
    )

    print("\nKEYWORD RESULTS:")

    for rank, result in enumerate(keyword_results, start=1):
        print(f"{rank}. {result.get('path')}")

    print("\nSEMANTIC RESULTS:")

    for rank, result in enumerate(semantic_results, start=1):
        print(
            f"{rank}. {result.get('path')} "
            f"(similarity={result.get('similarity_score', 0):.4f})"
        )

def evaluate_search():
    with open(DATASET_PATH, "r", encoding="utf-8") as file:
        test_cases = json.load(file)

    hits = 0
    reciprocal_rank_sum = 0.0

    with SessionLocal() as db:
        diagnose_query(db, "initialize application", REPOSITORY_ID)
        for test in test_cases:
            query = test["query"]

            # Support multiple acceptable paths.
            expected_paths = test.get("expected_paths")

            # Backward compatibility with the old dataset format.
            if expected_paths is None:
                expected_paths = [test["expected_path"]]

            results = hybrid_search(
                db=db,
                repository_id=REPOSITORY_ID,
                query=query,
                limit=LIMIT,
            )

            found_rank = None
            found_path = None

            for rank, result in enumerate(results, start=1):
                result_path = result.get("path")

                if result_path in expected_paths:
                    found_rank = rank
                    found_path = result_path
                    break

            if found_rank is not None:
                hits += 1
                reciprocal_rank_sum += 1.0 / found_rank

            rank_display = found_rank if found_rank is not None else "Not found"

            print(f"\nQuery: {query}")
            print(f"Expected files: {expected_paths}")
            print(f"Matched file: {found_path or 'None'}")
            print(f"Rank: {rank_display}")

            if results:
                print("Top results:")

                for rank, result in enumerate(results, start=1):
                    print(
                        f"  {rank}. {result.get('path')} "
                        f"(score={result.get('hybrid_score', 0):.6f})"
                    )
            else:
                print("Top results: No results")

    total = len(test_cases)

    if total == 0:
        print("No test cases found.")
        return

    recall_at_5 = hits / total
    mrr = reciprocal_rank_sum / total

    print("\n========== EVALUATION SUMMARY ==========")
    print(f"Queries tested: {total}")
    print(f"Recall@{LIMIT}: {recall_at_5:.2%}")
    print(f"MRR: {mrr:.4f}")
    print("========================================")


if __name__ == "__main__":
    evaluate_search()