"""Internal domain models — the shared vocabulary of the RAG pipeline.

These are deliberately separate from the API schemas in app/models/schemas.py
(which describe the HTTP boundary). Domain models flow *between* components
(parser -> chunker -> embedder -> vector store); schemas flow *over the wire*.
Keeping them apart means the API can evolve without disturbing the engine,
and vice-versa (Single Responsibility / stable core).
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ParsedPage:
    """One page of extracted text from a source document."""

    source_file: str        # e.g. "AppleInc.pdf"
    page_number: int        # 1-based, preserved so citations can point at a page
    text: str


@dataclass
class Chunk:
    """A retrievable unit: a slice of a page, plus everything needed for
    storage, citation, and (optionally) its embedding vector."""

    chunk_id: str           # stable, deterministic id -> idempotent re-ingest
    text: str
    source_file: str
    company: str
    page_number: int
    embedding: list[float] | None = None
    metadata: dict = field(default_factory=dict)


@dataclass
class SearchHit:
    """A chunk returned by retrieval, with its relevance score (used in Day 3)."""

    chunk: Chunk
    score: float


@dataclass
class IngestionResult:
    """Outcome of ingesting one document — returned up to the API layer."""

    source_file: str
    company: str
    pages_parsed: int
    chunks_created: int
    chunks_stored: int
