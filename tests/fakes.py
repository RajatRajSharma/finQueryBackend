"""In-memory fake implementations of the engine interfaces.

These exist purely so the pipeline can be tested with NO Qdrant, NO API key,
and NO real PDFs. That they're easy to write is the whole point of coding
against interfaces — the same IngestionService/RetrievalService that run with
Gemini + Qdrant in production run here with these fakes in a millisecond.
"""

from __future__ import annotations

from app.core.domain import Chunk, ParsedPage, SearchHit
from app.core.interfaces import (
    Chunker,
    DocumentParser,
    Embedder,
    LLMProvider,
    Reranker,
    VectorStore,
)


class FakeParser(DocumentParser):
    """Returns canned pages instead of reading a real file."""

    def __init__(self, pages: list[ParsedPage]) -> None:
        self._pages = pages

    def parse(self, file_path: str, source_name: str) -> list[ParsedPage]:
        return self._pages


class FakeChunker(Chunker):
    """One chunk per page — deterministic, no tokenizer needed."""

    def chunk(self, pages: list[ParsedPage], company: str) -> list[Chunk]:
        return [
            Chunk(
                chunk_id=f"{p.source_file}::p{p.page_number}::c0",
                text=p.text,
                source_file=p.source_file,
                company=company,
                page_number=p.page_number,
            )
            for p in pages
        ]


class FakeEmbedder(Embedder):
    """Deterministic toy embeddings — length-based, no network calls."""

    def __init__(self, dimension: int = 8) -> None:
        self._dimension = dimension

    @property
    def dimension(self) -> int:
        return self._dimension

    def _vec(self, text: str) -> list[float]:
        # Cheap deterministic vector: seeded by char codes, fixed length.
        base = [float((ord(c) % 17) / 17) for c in text[: self._dimension]]
        return (base + [0.0] * self._dimension)[: self._dimension]

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        return [self._vec(t) for t in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._vec(text)


class FakeVectorStore(VectorStore):
    """In-memory store. search() returns the most recently upserted chunks."""

    def __init__(self) -> None:
        self._chunks: list[Chunk] = []
        self.ensured_dimension: int | None = None

    def ensure_collection(self, dimension: int) -> None:
        self.ensured_dimension = dimension

    def upsert(self, chunks: list[Chunk]) -> int:
        self._chunks.extend(chunks)
        return len(chunks)

    def search(self, embedding: list[float], top_k: int) -> list[SearchHit]:
        return [SearchHit(chunk=c, score=1.0) for c in self._chunks[:top_k]]

    def health_check(self) -> bool:
        return True


class FakeLLM(LLMProvider):
    """Echoes a deterministic answer; records the prompt it was given."""

    def __init__(self) -> None:
        self.last_prompt: str | None = None

    def generate(self, prompt: str) -> str:
        self.last_prompt = prompt
        return "FAKE_ANSWER"


class FakeReranker(Reranker):
    """Deterministic reranker: reverses the candidate order and keeps top_n.

    Reversing makes the reorder observable in tests (the last candidate becomes
    first); the descending scores prove the reranker's score replaces the
    store's. Records the pool size it was handed so tests can assert over-fetch.
    """

    def __init__(self) -> None:
        self.last_pool_size: int | None = None

    def rerank(
        self, question: str, hits: list[SearchHit], top_n: int
    ) -> list[SearchHit]:
        self.last_pool_size = len(hits)
        reversed_hits = list(reversed(hits))[:top_n]
        return [
            SearchHit(chunk=h.chunk, score=1.0 - i * 0.01)
            for i, h in enumerate(reversed_hits)
        ]
