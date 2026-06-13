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
from app.core.interfaces import Embedder, VectorStore


class RetrievalService:
    def __init__(self, embedder: Embedder, vector_store: VectorStore, top_k: int) -> None:
        self._embedder = embedder
        self._store = vector_store
        self._top_k = top_k

    def retrieve(self, question: str, top_k: int | None = None) -> list[SearchHit]:
        query_vector = self._embedder.embed_query(question)
        return self._store.search(query_vector, top_k or self._top_k)
