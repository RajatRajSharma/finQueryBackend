"""Cohere client — the ONLY file that imports the cohere SDK.

Holds the Cohere-backed Reranker. Reranking takes the ~20 candidate chunks from
hybrid/dense retrieval and lets a cross-encoder re-score them for true relevance
to the question, keeping only the best few before generation — the single
biggest answer-quality lever in Week 2.

Swap to another reranker (e.g. a local cross-encoder, Voyage, Jina) by writing a
sibling class that satisfies `Reranker` and registering it in factory.py;
nothing else in the query pipeline changes.

Lazy-imported by the factory ONLY when ENABLE_RERANK is true, so the cohere SDK
is not a hard dependency for the Week 1 / rerank-off path.
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

import cohere

from app.core.domain import SearchHit
from app.core.errors import ConfigurationError, UpstreamServiceError
from app.core.interfaces import Reranker


@contextmanager
def _translate_cohere_errors(action: str) -> Iterator[None]:
    """Turn cohere SDK failures into a clean UpstreamServiceError -> HTTP 503.

    Mirrors gemini_client._translate_gemini_errors. The catch is intentionally
    broad because this wrapper does nothing but the network call + result
    mapping; tighten to cohere's concrete error type once it's live-tested.
    """
    try:
        yield
    except Exception as exc:  # noqa: BLE001 — any SDK/transport failure is "upstream"
        raise UpstreamServiceError(
            f"Cohere failed while {action}: {exc}. "
            "This is usually transient — please retry shortly."
        ) from exc


class CohereReranker(Reranker):
    def __init__(self, api_key: str, model: str) -> None:
        if not api_key:
            raise ConfigurationError(
                "COHERE_API_KEY is empty - set it in .env (or ENABLE_RERANK=false)."
            )
        self._client = cohere.Client(api_key=api_key)
        self._model = model

    def rerank(
        self, question: str, hits: list[SearchHit], top_n: int
    ) -> list[SearchHit]:
        if not hits:
            return []

        documents = [hit.chunk.text for hit in hits]
        with _translate_cohere_errors("reranking candidates"):
            response = self._client.rerank(
                model=self._model,
                query=question,
                documents=documents,
                top_n=min(top_n, len(hits)),
            )

        # Cohere returns results referencing the original index + a relevance
        # score; map back to our SearchHit, replacing the score with Cohere's.
        reranked: list[SearchHit] = []
        for result in response.results:
            original = hits[result.index]
            reranked.append(
                SearchHit(chunk=original.chunk, score=float(result.relevance_score))
            )
        return reranked
