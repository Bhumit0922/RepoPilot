
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor
import logging
from urllib.parse import quote, urlparse

import httpx


GITHUB_API = "https://api.github.com"

ALLOWED_EXTENSIONS = {
    ".py", ".js", ".jsx", ".ts", ".tsx",
    ".java", ".c", ".h", ".cpp", ".hpp",
    ".go", ".rs", ".rb", ".php",
    ".html", ".css", ".scss",
    ".json", ".yaml", ".yml", ".toml",
    ".md", ".sql", ".sh",
}

IGNORED_DIRECTORIES = {
    ".git", ".venv", "venv", "node_modules",
    "__pycache__", ".next", "dist", "build",
    "coverage", ".pytest_cache",
}

SENSITIVE_FILENAMES = {
    ".env", ".env.local", ".env.production",
    "id_rsa", "id_ed25519",
}

MAX_FILES = 100
MAX_FILE_BYTES = 200_000
MAX_TOTAL_BYTES = 5_000_000
MAX_CONCURRENT_DOWNLOADS = 8

logger = logging.getLogger(__name__)


@dataclass
class SourceFile:
    path: str
    sha: str
    language: str
    content: str


def parse_github_url(repository_url: str) -> tuple[str, str]:
    """Accept only standard public GitHub repository URLs."""

    parsed = urlparse(repository_url.strip())

    if parsed.scheme != "https" or parsed.hostname != "github.com":
        raise ValueError(
            "Provide a public repository URL beginning with "
            "https://github.com/"
        )

    parts = parsed.path.strip("/").split("/")

    if (
        len(parts) != 2
        or not all(parts)
        or any(part in {".", ".."} for part in parts)
        or parts[0].startswith(".")
        or parts[1].startswith(".")
    ):
        raise ValueError(
            "URL must have the format https://github.com/owner/repository"
        )

    owner, repo = parts

    if repo.endswith(".git"):
        repo = repo[:-4]

    return owner, repo


def language_from_path(path: str) -> str:
    suffix = "." + path.rsplit(".", 1)[-1].lower() if "." in path else ""

    languages = {
        ".py": "python",
        ".js": "javascript",
        ".jsx": "javascript",
        ".ts": "typescript",
        ".tsx": "tsx",
        ".java": "java",
        ".c": "c",
        ".h": "c",
        ".cpp": "cpp",
        ".hpp": "cpp",
        ".go": "go",
        ".rs": "rust",
        ".rb": "ruby",
        ".php": "php",
        ".html": "html",
        ".css": "css",
        ".scss": "scss",
        ".json": "json",
        ".yaml": "yaml",
        ".yml": "yaml",
        ".toml": "toml",
        ".md": "markdown",
        ".sql": "sql",
        ".sh": "bash",
    }

    return languages.get(suffix, "text")


def should_include_file(path: str, size: int) -> bool:
    parts = path.replace("\\", "/").split("/")
    filename = parts[-1].lower()

    if any(part.lower() in IGNORED_DIRECTORIES for part in parts[:-1]):
        return False

    if filename in SENSITIVE_FILENAMES or filename.startswith(".env"):
        return False

    if filename.endswith((".pem", ".key", ".p12", ".pfx")):
        return False

    if size <= 0 or size > MAX_FILE_BYTES:
        return False

    suffix = "." + filename.rsplit(".", 1)[-1] if "." in filename else ""

    return suffix in ALLOWED_EXTENSIONS


def fetch_repository(repository_url: str) -> tuple[str, str, list[SourceFile]]:
    owner, repo = parse_github_url(repository_url)

    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "RepoPilot-Portfolio",
    }

    with httpx.Client(
        timeout=20.0,
        follow_redirects=False,
        headers=headers,
    ) as client:
        response = client.get(
            f"{GITHUB_API}/repos/{owner}/{repo}"
        )

        if response.status_code == 404:
            raise ValueError(
                "Repository not found or not publicly accessible."
            )

        response.raise_for_status()
        metadata = response.json()

        if metadata.get("private"):
            raise ValueError(
                "Private repositories are not supported in this milestone."
            )

        branch = metadata["default_branch"]

        tree_url = (
            f"{GITHUB_API}/repos/{owner}/{repo}/git/trees/"
            f"{quote(branch, safe='/')}?recursive=1"
        )

        tree_response = client.get(tree_url)
        tree_response.raise_for_status()
        tree_data = tree_response.json()

        if tree_data.get("truncated"):
            raise ValueError(
                "This repository is too large for the initial "
                "ingestion implementation."
            )

        # Select a bounded set before downloading. Fetching each raw file
        # serially made larger repositories take one full network round trip
        # per file and could exceed the API client's request timeout.
        selected_entries = []
        total_bytes = 0

        for entry in tree_data.get("tree", []):
            if entry.get("type") != "blob":
                continue

            path = entry["path"]
            size = entry.get("size", 0)

            if not should_include_file(path, size):
                continue

            if len(selected_entries) >= MAX_FILES:
                break

            if total_bytes + size > MAX_TOTAL_BYTES:
                break

            selected_entries.append(entry)
            total_bytes += size

        logger.info(
            "Downloading %d source files from %s/%s (up to %d bytes)",
            len(selected_entries), owner, repo, total_bytes,
        )

        def download(entry: dict) -> SourceFile | None:
            path = entry["path"]
            raw_url = (
                f"https://raw.githubusercontent.com/{owner}/{repo}/"
                f"{quote(branch, safe='/')}/{quote(path, safe='/')}"
            )
            try:
                file_response = client.get(raw_url)
                if file_response.status_code != 200:
                    logger.debug(
                        "Skipping %s: raw GitHub returned HTTP %d",
                        path, file_response.status_code,
                    )
                    return None

                content_bytes = file_response.content
                if len(content_bytes) > MAX_FILE_BYTES:
                    return None

                content = content_bytes.decode("utf-8")
                if "\x00" in content:
                    return None
                return SourceFile(
                    path=path,
                    sha=entry["sha"],
                    language=language_from_path(path),
                    content=content,
                )
            except UnicodeDecodeError:
                return None

        # executor.map preserves tree order while keeping network use bounded.
        with ThreadPoolExecutor(max_workers=MAX_CONCURRENT_DOWNLOADS) as pool:
            files = [
                source_file
                for source_file in pool.map(download, selected_entries)
                if source_file is not None
            ]

        logger.info(
            "Downloaded %d readable source files from %s/%s",
            len(files), owner, repo,
        )

    if not files:
        raise ValueError(
            "No supported, readable source files were found."
        )

    canonical_url = f"https://github.com/{owner}/{repo}"

    return canonical_url, branch, files
