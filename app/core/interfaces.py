"""Abstract contracts for every swappable part of the RAG engine.

This module is the backbone of the architecture's flexibility. Every concrete
implementation (Gemini, Qdrant, pypdf, ...) depends on these abstractions, and
every service depends on these abstractions too — never on a concrete vendor.

That is the Dependency Inversion Principle: high-level policy (IngestionService,
the query pipeline) and low-level detail (GeminiEmbedder, QdrantVectorStore)
both point at the SAME interface. Swapping Gemini for OpenAI means writing one
new class that satisfies `Embedder` and changing one line in factory.py — no
service, router, or pipeline is touched (Open/Closed Principle).

Interfaces are intentionally small (Interface Segregation): a parser only knows
how to parse; an embedder only knows how to embed.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from app.core.domain import Chunk, ParsedPage, SearchHit


class DocumentParser(ABC):
    """Turns a file on disk into a list of pages with text + page numbers."""

    @abstractmethod
    def parse(self, file_path: str, source_name: str) -> list[ParsedPage]:
        ...


class Chunker(ABC):
    """Splits parsed pages into retrieval-sized chunks, preserving page info."""

    @abstractmethod
    def chunk(self, pages: list[ParsedPage], company: str) -> list[Chunk]:
        ...


class Embedder(ABC):
    """Converts text into vectors. Implementations wrap a single vendor SDK."""

    @property
    @abstractmethod
    def dimension(self) -> int:
        """Vector size — the vector store needs this to size its collection."""
        ...

    @abstractmethod
    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Embed documents for storage (batched)."""
        ...

    @abstractmethod
    def embed_query(self, text: str) -> list[float]:
        """Embed a single user query (may use a different task/instruction)."""
        ...


class VectorStore(ABC):
    """Persists and searches embedded chunks."""

    @abstractmethod
    def ensure_collection(self, dimension: int) -> None:
        """Create the collection if it doesn't exist (idempotent)."""
        ...

    @abstractmethod
    def upsert(self, chunks: list[Chunk]) -> int:
        """Store embedded chunks; returns how many points were written."""
        ...

    @abstractmethod
    def search(self, embedding: list[float], top_k: int) -> list[SearchHit]:
        """Nearest-neighbour search (used by the Day 3 query pipeline)."""
        ...

    @abstractmethod
    def health_check(self) -> bool:
        """True if the store is reachable — powers /health/ready."""
        ...


class LLMProvider(ABC):
    """Generates an answer from a prompt. Implemented in Day 3 (generation)."""

    @abstractmethod
    def generate(self, prompt: str) -> str:
        ...


class Reranker(ABC):
    """Re-scores retrieved chunks for true relevance and keeps the best few.

    Week 2 quality lever (the cross-encoder half of the query pipeline). Takes
    the over-fetched candidate hits and returns at most `top_n`, reordered by
    the reranker's own relevance score. Like every other contract here it's
    vendor-agnostic — Cohere today, swap by adding one class + one factory line.
    """

    @abstractmethod
    def rerank(
        self, question: str, hits: list[SearchHit], top_n: int
    ) -> list[SearchHit]:
        ...
