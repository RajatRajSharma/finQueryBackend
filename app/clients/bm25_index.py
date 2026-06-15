"""BM25 keyword retriever — the sparse half of hybrid search.

The ONLY file that imports rank-bm25. Holds an in-memory BM25Okapi index over
the stored chunk text and scores a query against it lexically. This complements
dense vector search: BM25 reliably matches exact tokens (ticker symbols,
"Q4 2024", line-item names) that embeddings can blur.

**Where the index lives (a deliberate trade-off):** it's built in-memory from
whatever `VectorStore.all_chunks()` returns, once, when the factory first needs
it (see `factory.get_sparse_retriever`). For the demo corpus (a few hundred
short chunks) building is milliseconds. The limitation: a document uploaded
*after* the index is built won't appear in BM25 until the index is rebuilt
(process restart, or a future `/admin/reindex`). Dense search (Qdrant) is always
fresh, so a new upload is still queryable — just not via the keyword half until
reindex. Persisting/refreshing the index is a Week 3+ concern.

Swap BM25 for another lexical engine by writing a sibling `SparseRetriever`;
nothing in the query pipeline changes.
"""

from __future__ import annotations

import re

from rank_bm25 import BM25Okapi

from app.core.domain import Chunk, SearchHit
from app.core.interfaces import SparseRetriever

# Cheap, dependency-free tokenizer: lowercase alphanumeric runs. Good enough for
# keyword matching over English filings; no stemming/stopwords on purpose (keeps
# it predictable and avoids dragging in NLTK).
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
