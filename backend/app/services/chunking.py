
import bisect

from tree_sitter_language_pack import get_parser


MAX_CHUNK_LINES = 80
MIN_BOUNDARY_LINES = 30

PARSER_LANGUAGES = {
    "python": "python",
    "javascript": "javascript",
    "typescript": "typescript",
    "tsx": "tsx",
    "java": "java",
    "c": "c",
    "cpp": "cpp",
    "go": "go",
    "rust": "rust",
    "ruby": "ruby",
    "php": "php",
    "html": "html",
    "css": "css",
    "json": "json",
    "yaml": "yaml",
    "bash": "bash",
}


def find_syntax_boundaries(
    content: str,
    language: str,
) -> set[int]:
    """Return candidate line boundaries using Tree-sitter."""

    parser_language = PARSER_LANGUAGES.get(language)

    if not parser_language:
        return set()

    try:
        content_bytes = content.encode("utf-8")
        parser = get_parser(parser_language)
        tree = parser.parse(content_bytes)

        # Store byte positions of newline characters.
        newline_offsets = [
            i for i, byte in enumerate(content_bytes)
            if byte == 10
        ]

        # Convert each syntax node's ending byte into a
        # 1-based line boundary without accessing end_point.
        return {
            bisect.bisect_left(
                newline_offsets,
                node.end_byte,
            ) + 1
            for node in tree.root_node.named_children
        }

    except Exception:
        # Parsing failures should not prevent basic ingestion.
        return set()


def chunk_source(
    content: str,
    language: str,
) -> list[dict]:
    """Split source into chunks while preserving line numbers."""

    lines = content.splitlines()

    if not lines:
        return []

    boundaries = find_syntax_boundaries(content, language)

    chunks = []
    start = 0

    while start < len(lines):
        hard_end = min(
            start + MAX_CHUNK_LINES,
            len(lines),
        )

        if hard_end == len(lines):
            end = hard_end
        else:
            candidates = [
                boundary
                for boundary in boundaries
                if start + MIN_BOUNDARY_LINES
                <= boundary
                <= hard_end
            ]

            # Prefer the latest valid syntax boundary.
            end = max(candidates) if candidates else hard_end

        chunk_text = "\n".join(lines[start:end])

        if chunk_text.strip():
            chunks.append({
                "chunk_index": len(chunks),
                "start_line": start + 1,
                "end_line": end,
                "content": chunk_text,
            })

        start = end

    return chunks
