"""RetrievalService — finds the chunks most relevant to a question.

Full query path:
    dense ─┐
           ├─ fuse (HYBRID_ALPHA) ─ pool ─ rerank ─ top_k ─► generation
    sparse ┘
The sparse and rerank stages are optional and flag-gated; with neither, this is
a plain dense-only retriever.
"""

from __future__ import annotations

from app.core.domain import SearchHit
from app.core.interfaces import Embedder, Reranker, SparseRetriever, VectorStore


def _normalize(hits: list[SearchHit]) -> dict[str, float]:
    """Min-max normalise a hit list's scores to [0,1], keyed by chunk_id.

    Dense (cosine) and sparse (BM25) scores are on different scales, so each list
    is normalised independently before fusion.
    """
    if not hits:
        return {}
    scores = [h.score for h in hits]
    lo, hi = min(scores), max(scores)
    span = hi - lo
    if span == 0:
        return {h.chunk.chunk_id: 1.0 for h in hits}
    return {h.chunk.chunk_id: (h.score - lo) / span for h in hits}


def fuse(
    dense: list[SearchHit], sparse: list[SearchHit], alpha: float
) -> list[SearchHit]:
    """Weighted fusion of dense + sparse hits.

    combined = alpha * dense_norm + (1 - alpha) * sparse_norm  (missing → 0).
    alpha=1.0 → dense only, alpha=0.0 → sparse only. Returns hits sorted by the
    combined score, deduped by chunk_id.
    """
    dense_norm = _normalize(dense)
    sparse_norm = _normalize(sparse)
    chunks = {h.chunk.chunk_id: h.chunk for h in [*dense, *sparse]}

    fused: list[SearchHit] = []
    for chunk_id, chunk in chunks.items():
        score = alpha * dense_norm.get(chunk_id, 0.0) + (1 - alpha) * sparse_norm.get(
            chunk_id, 0.0
        )
        fused.append(SearchHit(chunk=chunk, score=score))
    fused.sort(key=lambda h: h.score, reverse=True)
    return fused


class RetrievalService:
    def __init__(
        self,
        embedder: Embedder,
        vector_store: VectorStore,
        top_k: int,
        reranker: Reranker | None = None,
        sparse: SparseRetriever | None = None,
        candidates: int | None = None,
        hybrid_alpha: float = 0.5,
    ) -> None:
        self._embedder = embedder
        self._store = vector_store
        self._top_k = top_k
        self._reranker = reranker
        self._sparse = sparse
        # Defaults to top_k so over-fetch (for fuse/rerank) is opt-in.
        self._candidates = candidates or top_k
        self._alpha = hybrid_alpha

    def retrieve(self, question: str, top_k: int | None = None) -> list[SearchHit]:
        k = top_k or self._top_k
        query_vector = self._embedder.embed_query(question)

        # Fast path: dense nearest-neighbour only (no hybrid, no rerank).
        if self._sparse is None and self._reranker is None:
            return self._store.search(query_vector, k)

        # Over-fetch a wider candidate pool for fusion/rerank.
        n = max(self._candidates, k)
        dense_hits = self._store.search(query_vector, n)

        if self._sparse is not None:
            sparse_hits = self._sparse.search(question, n)
            pool = fuse(dense_hits, sparse_hits, self._alpha)[:n]
        else:
            pool = dense_hits

        if self._reranker is not None:
            return self._reranker.rerank(question, pool, top_n=k)
        return pool[:k]
