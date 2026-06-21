"""In-memory fake implementations of the engine interfaces.

Let the pipeline be tested with no Qdrant, no API key, and no real PDFs — the
same services that run on Gemini + Qdrant in production run here on these fakes.
"""

from __future__ import annotations

from app.core.domain import (
    Chunk,
    EvalRecord,
    EvalReport,
    ParsedPage,
    RouteDecision,
    SearchHit,
    WebResult,
)
from app.core.interfaces import (
    Chunker,
    DocumentParser,
    Embedder,
    Evaluator,
    LLMProvider,
    QueryRouter,
    Reranker,
    SparseRetriever,
    VectorStore,
    WebSearchTool,
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
        # Deterministic vector seeded by char codes, fixed length.
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

    def all_chunks(self) -> list[Chunk]:
        return list(self._chunks)

    def delete_except(self, source_files: list[str]) -> int:
        if not source_files:
            raise ValueError("delete_except needs a non-empty keep-list (refusing to wipe all).")
        keep = set(source_files)
        before = len(self._chunks)
        self._chunks = [c for c in self._chunks if c.source_file in keep]
        return before - len(self._chunks)

    def health_check(self) -> bool:
        return True


class FakeLLM(LLMProvider):
    """Echoes a deterministic answer; records the prompt it was given."""

    def __init__(self) -> None:
        self.last_prompt: str | None = None

    def generate(self, prompt: str) -> str:
        self.last_prompt = prompt
        return "FAKE_ANSWER"

    def generate_stream(self, prompt: str):
        self.last_prompt = prompt
        for token in ("FAKE", "_", "ANSWER"):
            yield token


class FakeEvaluator(Evaluator):
    """Records what it was given and returns flat 1.0s — no ragas/API needed."""

    def __init__(self) -> None:
        self.seen: list[EvalRecord] = []

    def evaluate(self, records: list[EvalRecord]) -> EvalReport:
        self.seen = records
        per_q = [
            {"question": r.question, "faithfulness": 1.0, "answer_relevancy": 1.0}
            for r in records
        ]
        metrics = {"faithfulness": 1.0, "answer_relevancy": 1.0} if records else {}
        return EvalReport(metrics=metrics, per_question=per_q, num_questions=len(records))


class FakeQueryRouter(QueryRouter):
    """Returns a preset RouteDecision so tests can force each agent branch."""

    def __init__(self, decision: RouteDecision) -> None:
        self._decision = decision

    def route(self, question: str) -> RouteDecision:
        return self._decision


class FakeWebSearchTool(WebSearchTool):
    """Returns canned web results, no network."""

    def __init__(self, results: list[WebResult] | None = None) -> None:
        self._results = results or []
        self.last_query: str | None = None

    def search(self, query: str) -> list[WebResult]:
        self.last_query = query
        return self._results


class FakeSparseRetriever(SparseRetriever):
    """Returns pre-set hits, ignoring the query — you supply the sparse side of
    a fusion test and assert how it combines with the dense side."""

    def __init__(self, hits: list[SearchHit] | None = None) -> None:
        self._hits = hits or []
        self.indexed: list[Chunk] = []

    def index(self, chunks: list[Chunk]) -> None:
        self.indexed = list(chunks)

    def search(self, question: str, top_k: int) -> list[SearchHit]:
        return self._hits[:top_k]


class FakeReranker(Reranker):
    """Reverses candidate order and keeps top_n, so the reorder is observable
    (last becomes first) and descending scores replace the store's. Records the
    pool size handed in so tests can assert over-fetch."""

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
