"""Code indexer — chunks code files and embeds them into ChromaDB."""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path

import chromadb

from agentforge.config import CHROMA_COLLECTION, CHROMA_PERSIST_DIR

logger = logging.getLogger(__name__)

# File extensions to index
CODE_EXTENSIONS = {
    ".py",
    ".js",
    ".ts",
    ".jsx",
    ".tsx",
    ".java",
    ".go",
    ".rs",
    ".rb",
    ".cpp",
    ".c",
    ".h",
    ".cs",
    ".php",
    ".swift",
    ".kt",
    ".scala",
    ".sql",
    ".sh",
    ".yml",
    ".yaml",
    ".toml",
    ".json",
}

# Max file size to index (500KB)
MAX_FILE_SIZE = 500_000


def _get_chroma_client() -> chromadb.ClientAPI:
    """Create a persistent ChromaDB client."""
    Path(CHROMA_PERSIST_DIR).mkdir(parents=True, exist_ok=True)
    return chromadb.PersistentClient(path=CHROMA_PERSIST_DIR)


def _chunk_code(content: str, filename: str, chunk_size: int = 100) -> list[dict]:
    """Split code into line-based chunks with overlap.

    Each chunk is ~chunk_size lines with 10-line overlap for context.
    """
    lines = content.split("\n")
    chunks = []
    overlap = 10
    start = 0

    while start < len(lines):
        end = min(start + chunk_size, len(lines))
        chunk_lines = lines[start:end]
        chunk_text = "\n".join(chunk_lines)

        chunk_id = hashlib.sha256(f"{filename}:{start}:{end}".encode()).hexdigest()[:16]

        chunks.append(
            {
                "id": chunk_id,
                "text": chunk_text,
                "metadata": {
                    "filename": filename,
                    "line_start": start + 1,
                    "line_end": end,
                    "total_lines": len(lines),
                },
            }
        )

        start = end - overlap if end < len(lines) else end

    return chunks


def index_directory(directory: str) -> int:
    """Index all code files in a directory into ChromaDB.

    Returns the number of chunks indexed.
    """
    client = _get_chroma_client()
    collection = client.get_or_create_collection(
        name=CHROMA_COLLECTION,
        metadata={"hnsw:space": "cosine"},
    )

    total_chunks = 0
    root = Path(directory).resolve()

    for filepath in root.rglob("*"):
        if not filepath.is_file():
            continue
        if filepath.suffix not in CODE_EXTENSIONS:
            continue
        if filepath.stat().st_size > MAX_FILE_SIZE:
            continue
        # Skip common non-source directories
        rel = str(filepath.relative_to(root))
        if any(
            part.startswith(".") or part in ("node_modules", "__pycache__", "venv", ".venv", "dist", "build")
            for part in filepath.parts
        ):
            continue

        try:
            content = filepath.read_text(encoding="utf-8", errors="ignore")
        except Exception as e:
            logger.warning(f"Failed to read {filepath}: {e}")
            continue

        chunks = _chunk_code(content, rel)
        if not chunks:
            continue

        # Upsert into ChromaDB
        collection.upsert(
            ids=[c["id"] for c in chunks],
            documents=[c["text"] for c in chunks],
            metadatas=[c["metadata"] for c in chunks],
        )
        total_chunks += len(chunks)

    logger.info(f"Indexed {total_chunks} chunks from {directory}")
    return total_chunks


def index_file(filepath: str) -> int:
    """Index a single file. Returns chunk count."""
    client = _get_chroma_client()
    collection = client.get_or_create_collection(
        name=CHROMA_COLLECTION,
        metadata={"hnsw:space": "cosine"},
    )

    path = Path(filepath)
    content = path.read_text(encoding="utf-8", errors="ignore")
    chunks = _chunk_code(content, path.name)

    if chunks:
        collection.upsert(
            ids=[c["id"] for c in chunks],
            documents=[c["text"] for c in chunks],
            metadatas=[c["metadata"] for c in chunks],
        )

    return len(chunks)
