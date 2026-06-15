"""Query router — POST /query (retrieve -> generate -> cite).

Thin orchestration over three injected services. Note the router doesn't know
about Gemini or Qdrant — it composes RetrievalService + GenerationService +
the citations helper, all resolved from the factory. Week 1 returns the full
answer in one response; SSE token streaming is added in Week 2.
"""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends
from sse_starlette.sse import EventSourceResponse

from app.core.factory import get_generation_service, get_retrieval_service
from app.models.schemas import Citation, QueryRequest, QueryResponse
from app.services.citations import build_citations
from app.services.generation import GenerationService
from app.services.retrieval import RetrievalService

router = APIRouter(tags=["query"])


@router.post("/query", response_model=QueryResponse)
def query(
    request: QueryRequest,
    retrieval: RetrievalService = Depends(get_retrieval_service),
    generation: GenerationService = Depends(get_generation_service),
) -> QueryResponse:
    # 1. Retrieve relevant chunks (dense vector search).
    hits = retrieval.retrieve(request.question, top_k=request.top_k)

    # 2. Generate an answer grounded in those chunks.
    answer = generation.generate_answer(request.question, [h.chunk for h in hits])

    # 3. Attach citations (source file + page) as proof.
    citations = [Citation(**c) for c in build_citations(hits)]

    return QueryResponse(answer=answer, citations=citations)


@router.post("/query/stream")
def query_stream(
    request: QueryRequest,
    retrieval: RetrievalService = Depends(get_retrieval_service),
    generation: GenerationService = Depends(get_generation_service),
) -> EventSourceResponse:
    """Streaming variant of /query (SSE).

    Retrieval runs up front (so citations are known), then the answer is streamed
    token-by-token as `token` events, followed by a single `citations` event and
    a `done` sentinel. The frontend appends tokens live and renders citation
    chips on the final event. `POST /query` remains the one-shot path for
    evals/tests.
    """
    hits = retrieval.retrieve(request.question, top_k=request.top_k)
    citations = build_citations(hits)
    contexts = [h.chunk for h in hits]

    def event_stream():
        # Stream answer deltas. Errors raised mid-stream (e.g. a Gemini 503)
        # are sent as an `error` event so the client can show a message instead
        # of a silently truncated answer.
        try:
            for delta in generation.generate_answer_stream(request.question, contexts):
                yield {"event": "token", "data": delta}
        except Exception as exc:  # noqa: BLE001 — surface upstream failures to the client
            yield {"event": "error", "data": str(exc)}
            return
        yield {"event": "citations", "data": json.dumps(citations)}
        yield {"event": "done", "data": ""}

    return EventSourceResponse(event_stream())
