"""Cohere client — the only file that imports the cohere SDK.

Cohere-backed Reranker: cross-encoder re-scores the ~20 retrieval candidates by
relevance, keeping only the best few before generation.

Lazy-imported by the factory only when ENABLE_RERANK is true, so the cohere SDK
isn't a hard dependency on the rerank-off path.
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

    Catch is broad because the wrapper only does the network call + mapping;
    tighten to cohere's concrete error type once it's live-tested.
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

        # Cohere results reference the original index; map back to SearchHit
        # with Cohere's relevance score.
        reranked: list[SearchHit] = []
        for result in response.results:
            original = hits[result.index]
            reranked.append(
                SearchHit(chunk=original.chunk, score=float(result.relevance_score))
            )
        return reranked
