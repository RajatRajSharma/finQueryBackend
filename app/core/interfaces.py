"""Abstract contracts for every swappable part of the RAG engine.

Services depend on these abstractions, never on a concrete vendor; the concrete
class is selected in factory.py. Swapping a vendor means one new class + one
factory line.
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
        """Nearest-neighbour search."""
        ...

    @abstractmethod
    def all_chunks(self) -> list[Chunk]:
        """Return every stored chunk (text + metadata, no vectors needed).

        Used to (re)build the BM25 keyword index so the sparse half needs no
        second source of truth.
        """
        ...

    @abstractmethod
    def delete_except(self, source_files: list[str]) -> int:
        """Delete every chunk whose `source_file` is NOT in `source_files`.

        Returns how many points were deleted. An empty keep-list would wipe the
        collection, so callers must guard against that.
        """
        ...

    @abstractmethod
    def health_check(self) -> bool:
        """True if the store is reachable — powers /health/ready."""
        ...


class LLMProvider(ABC):
    """Generates an answer from a prompt."""

    @abstractmethod
    def generate(self, prompt: str) -> str:
        ...

    @abstractmethod
    def generate_stream(self, prompt: str) -> Iterator[str]:
        """Yield the answer incrementally as text deltas (for SSE streaming).

        Same prompt contract as `generate`; kept separate so evals/tests can use
        the one-shot call while the API streams token-by-token.
        """
        ...


class Reranker(ABC):
    """Re-scores retrieved chunks for relevance and keeps the best few.

    Takes the over-fetched candidate hits and returns at most `top_n`, reordered
    by the reranker's own relevance score.
    """

    @abstractmethod
    def rerank(
        self, question: str, hits: list[SearchHit], top_n: int
    ) -> list[SearchHit]:
        ...


class SparseRetriever(ABC):
    """Keyword/lexical retrieval (the BM25 half of hybrid search).

    Complements dense search: BM25 nails exact terms — ticker symbols, "Q4 2024",
    line-item names — that embeddings can blur. `index` (re)builds from a set of
    chunks; `search` returns the best `top_k` by lexical score.
    """

    @abstractmethod
    def index(self, chunks: list[Chunk]) -> None:
        ...

    @abstractmethod
    def search(self, question: str, top_k: int) -> list[SearchHit]:
        ...


class QueryRouter(ABC):
    """Decides how to handle a question before retrieving.

    Returns a RouteDecision — answer from docs, clarify, or fall back to web
    search. Implementation lives in services/agent.py.
    """

    @abstractmethod
    def route(self, question: str) -> RouteDecision:
        ...


class WebSearchTool(ABC):
    """External web search — the agent's fallback when a question isn't covered
    by the uploaded reports (e.g. post-filing news, current prices).
    """

    @abstractmethod
    def search(self, query: str) -> list[WebResult]:
        ...


class Evaluator(ABC):
    """Scores a batch of answered questions (RAGAS evaluation).

    Takes EvalRecords (question + answer + contexts + ground truth) and returns
    an EvalReport of averaged quality metrics.
    """

    @abstractmethod
    def evaluate(self, records: list[EvalRecord]) -> EvalReport:
        ...
