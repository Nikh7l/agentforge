"""Retriever — queries ChromaDB for relevant code context."""

from __future__ import annotations

import logging
from pathlib import Path

import chromadb

from agentforge.config import CHROMA_COLLECTION, CHROMA_PERSIST_DIR

logger = logging.getLogger(__name__)


def _get_collection() -> chromadb.Collection | None:
    """Get the ChromaDB collection, or None if not initialized."""
    persist_dir = Path(CHROMA_PERSIST_DIR)
    if not persist_dir.exists():
        return None

    client = chromadb.PersistentClient(path=CHROMA_PERSIST_DIR)
    try:
        return client.get_collection(name=CHROMA_COLLECTION)
    except Exception:
        return None


def retrieve_context(query: str, top_k: int = 5) -> str:
    """Find relevant code chunks for the given query.

    Returns a formatted string of matching code chunks with metadata,
    or empty string if no collection exists.
    """
    collection = _get_collection()
    if collection is None:
        return ""

    try:
        results = collection.query(
            query_texts=[query],
            n_results=min(top_k, collection.count()),
        )
    except Exception as e:
        logger.warning(f"Retrieval failed: {e}")
        return ""

    if not results or not results["documents"] or not results["documents"][0]:
        return ""

    # Format context
    sections = []
    documents = results["documents"][0]
    metadatas = results["metadatas"][0] if results["metadatas"] else [{}] * len(documents)

    for doc, meta in zip(documents, metadatas, strict=False):
        filename = meta.get("filename", "unknown")
        line_start = meta.get("line_start", "?")
        line_end = meta.get("line_end", "?")
        sections.append(f"### {filename} (lines {line_start}-{line_end})\n```\n{doc}\n```")

    return "\n\n".join(sections)


def get_collection_stats() -> dict:
    """Return stats about the indexed collection."""
    collection = _get_collection()
    if collection is None:
        return {"indexed": False, "count": 0}

    return {
        "indexed": True,
        "count": collection.count(),
    }
