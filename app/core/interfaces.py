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
from typing import Iterator

from app.core.domain import (
    Chunk,
    EvalRecord,
    EvalReport,
    ParsedPage,
    RouteDecision,
    SearchHit,
    WebResult,
)


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
    def all_chunks(self) -> list[Chunk]:
        """Return every stored chunk (text + metadata, no vectors needed).

        Used to (re)build the Week 2 BM25 keyword index from what's already in
        the store, so the sparse half doesn't need a second source of truth.
        """
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

    @abstractmethod
    def generate_stream(self, prompt: str) -> Iterator[str]:
        """Yield the answer incrementally as text deltas (Week 2 SSE streaming).

        Same prompt contract as `generate`; the caller concatenates the deltas.
        Kept separate from `generate` so evals/tests can use the simple one-shot
        call while the API streams to the browser token-by-token.
        """
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


class SparseRetriever(ABC):
    """Keyword/lexical retrieval (the BM25 half of hybrid search).

    Complements dense vector search: BM25 nails exact terms — ticker symbols,
    "Q4 2024", line-item names — that embeddings can blur. `index` (re)builds the
    keyword index from a set of chunks; `search` returns the best `top_k` by
    lexical score. Kept behind an interface so the implementation (rank-bm25
    today) can be swapped without touching the query pipeline.
    """

    @abstractmethod
    def index(self, chunks: list[Chunk]) -> None:
        ...

    @abstractmethod
    def search(self, question: str, top_k: int) -> list[SearchHit]:
        ...


class QueryRouter(ABC):
    """The agentic layer: decides HOW to handle a question before retrieving.

    Returns a RouteDecision — answer from the documents, ask the user to
    clarify, or fall back to web search. This is what makes the system "agentic
    RAG" rather than a fixed pipeline. Vendor-agnostic like the rest: the LLM
    implementation lives in services/agent.py behind this port.
    """

    @abstractmethod
    def route(self, question: str) -> RouteDecision:
        ...


class WebSearchTool(ABC):
    """External web search — the agent's fallback when a question isn't covered
    by the uploaded reports (e.g. post-filing news, current prices).

    Kept behind a port so the provider (DuckDuckGo, Tavily, …) can be swapped,
    and so it's opt-in: the core demo never depends on an external search key.
    """

    @abstractmethod
    def search(self, query: str) -> list[WebResult]:
        ...


class Evaluator(ABC):
    """Scores a batch of answered questions (Week 3 RAGAS evaluation).

    Takes EvalRecords (question + pipeline answer + retrieved contexts +
    ground truth) and returns an EvalReport of averaged quality metrics. Behind a
    port so the scorer (RAGAS today, a fake in tests) is swappable and the
    /evals endpoint never imports the eval library directly.
    """

    @abstractmethod
    def evaluate(self, records: list[EvalRecord]) -> EvalReport:
        ...
