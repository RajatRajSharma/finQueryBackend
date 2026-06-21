"""BM25 keyword retriever — the sparse half of hybrid search.

The only file that imports rank-bm25. Holds an in-memory BM25Okapi index over
stored chunk text; matches exact tokens (tickers, "Q4 2024", line-item names)
that dense embeddings blur.

Gotcha: the index is built once from `VectorStore.all_chunks()` (see
`factory.get_sparse_retriever`). A document uploaded after build won't appear in
BM25 until a rebuild (process restart or `/admin/reindex`). Dense search stays
fresh, so new uploads are still queryable — just not via the keyword half.
"""

from __future__ import annotations

import re

from rank_bm25 import BM25Okapi

from app.core.domain import Chunk, SearchHit
from app.core.interfaces import SparseRetriever

# Tokenizer: lowercase alphanumeric runs. No stemming/stopwords on purpose
# (predictable, and avoids an NLTK dependency).
_TOKEN_RE = re.compile(r"[a-z0-9]+")


def _tokenize(text: str) -> list[str]:
    return _TOKEN_RE.findall(text.lower())


class Bm25Retriever(SparseRetriever):
    def __init__(self) -> None:
        self._chunks: list[Chunk] = []
        self._bm25: BM25Okapi | None = None

    def index(self, chunks: list[Chunk]) -> None:
        self._chunks = list(chunks)
        tokenized = [_tokenize(c.text) for c in self._chunks]
        # BM25Okapi rejects an empty corpus; leave it unbuilt and return [] later.
        self._bm25 = BM25Okapi(tokenized) if tokenized else None

    def search(self, question: str, top_k: int) -> list[SearchHit]:
        if self._bm25 is None or not self._chunks:
            return []
        scores = self._bm25.get_scores(_tokenize(question))
        # Rank by descending BM25 score, keep top_k (skip zero-score chunks).
        ranked = sorted(
            range(len(self._chunks)), key=lambda i: scores[i], reverse=True
        )
        hits: list[SearchHit] = []
        for i in ranked[:top_k]:
            if scores[i] <= 0:
                break
            hits.append(SearchHit(chunk=self._chunks[i], score=float(scores[i])))
        return hits
