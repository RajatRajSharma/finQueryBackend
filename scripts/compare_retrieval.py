"""Compare dense-only vs hybrid (dense + BM25) retrieval, side by side.

Embeds each question once, then runs pure dense search and hybrid fusion over
the same vector, printing the top chunks each returns. Isolates the retrieval
change without spending generation quota (one embed per question, reused).

    ./venv/Scripts/python.exe -m scripts.compare_retrieval

Needs Qdrant up + a populated collection + GEMINI_API_KEY. Re-run after tuning
HYBRID_ALPHA / RETRIEVE_CANDIDATES; record results in docs/tuning-runs.md.
"""

from __future__ import annotations

from app.clients.bm25_index import Bm25Retriever
from app.config import settings
from app.core.factory import get_embedder, get_vector_store
from app.services.retrieval import fuse

QUESTIONS = [
    "What were Apple's total net sales?",
    "What are the risk factors related to tariffs and trade?",
    "How did Services net sales perform?",
    "What is the share repurchase program?",
    "iPhone net sales change year over year",
]

TOP_K = settings.TOP_K
CANDIDATES = settings.RETRIEVE_CANDIDATES
ALPHA = settings.HYBRID_ALPHA


def _fmt(hits) -> str:
    return ", ".join(f"p{h.chunk.page_number}:{h.score:.3f}" for h in hits)


def main() -> None:
    embedder = get_embedder()
    store = get_vector_store()

    bm25 = Bm25Retriever()
    bm25.index(store.all_chunks())

    print(f"# dense vs hybrid (alpha={ALPHA}, candidates={CANDIDATES}, top_k={TOP_K})\n")
    for q in QUESTIONS:
        qvec = embedder.embed_query(q)  # reused by both modes
        dense = store.search(qvec, TOP_K)
        pool_dense = store.search(qvec, CANDIDATES)
        sparse = bm25.search(q, CANDIDATES)
        hybrid = fuse(pool_dense, sparse, ALPHA)[:TOP_K]

        print(f"Q: {q}")
        print(f"  dense : {_fmt(dense)}")
        print(f"  hybrid: {_fmt(hybrid)}")
        print()


if __name__ == "__main__":
    main()
