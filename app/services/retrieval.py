"""RetrievalService — finds the chunks most relevant to a question.

Week 1: dense vector search only (embed the question, nearest-neighbour search
in the vector store). Week 2 adds the BM25 sparse half + Cohere reranking — and
because this service depends only on the Embedder + VectorStore interfaces,
those upgrades slot in without the query router or generation ever changing.

This is the ONLY query-side component that touches the vector store, which is
why everything *else* in the query pipeline is testable without Qdrant.
"""

from __future__ import annotations

from app.core.domain import SearchHit
from app.core.interfaces import Embedder, Reranker, VectorStore


class RetrievalService:
    def __init__(
        self,
        embedder: Embedder,
        vector_store: VectorStore,
        top_k: int,
        reranker: Reranker | None = None,
        candidates: int | None = None,
    ) -> None:
        self._embedder = embedder
        self._store = vector_store
        self._top_k = top_k
        self._reranker = reranker
        # Only matters when reranking; defaults to top_k so over-fetch is opt-in.
        self._candidates = candidates or top_k

    def retrieve(self, question: str, top_k: int | None = None) -> list[SearchHit]:
        k = top_k or self._top_k
        query_vector = self._embedder.embed_query(question)

        if self._reranker is None:
            # Week 1 path, unchanged: dense nearest-neighbour search.
            return self._store.search(query_vector, k)

        # Week 2: over-fetch a wider pool, then keep the reranker's best k.
        pool = self._store.search(query_vector, max(self._candidates, k))
        return self._reranker.rerank(question, pool, top_n=k)
