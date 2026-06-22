"""Query router — POST /query and POST /query/stream.

Orchestrates the optional flag-gated agent and the retrieve→generate→cite
pipeline via injected services — no vendor imports here.

When ENABLE_AGENT is on, a QueryRouter classifies the question and the endpoint
branches:
  - answer_from_docs → the hybrid/rerank pipeline (also the default)
  - clarify          → return a one-line follow-up question instead of an answer
  - web_search       → fall back to the web tool (if ENABLE_WEB_SEARCH), else docs
When the agent is off, get_query_router() is None and only the docs path runs.
"""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends
from sse_starlette.sse import EventSourceResponse

from app.core.domain import ROUTE_ANSWER, ROUTE_CLARIFY, ROUTE_WEB, RouteDecision
from app.core.factory import (
    get_generation_service,
    get_query_router,
    get_retrieval_service,
    get_web_search_tool,
)
from app.core.interfaces import QueryRouter, WebSearchTool
from app.models.schemas import Citation, QueryRequest, QueryResponse, WebSource
from app.services.citations import build_citations
from app.services.generation import GenerationService
from app.services.retrieval import RetrievalService

router = APIRouter(tags=["query"])

_CLARIFY_FALLBACK = "Could you clarify your question — which company and metric?"


def _decide(question: str, router_: QueryRouter | None) -> RouteDecision:
    """Run the agent if enabled; otherwise default to answering from docs."""
    return router_.route(question) if router_ is not None else RouteDecision(ROUTE_ANSWER)


def _to_web_sources(results) -> list[WebSource]:
    return [WebSource(title=r.title, url=r.url, snippet=r.snippet) for r in results]


@router.post("/query", response_model=QueryResponse)
def query(
    request: QueryRequest,
    use_hybrid: bool | None = None,
    use_rerank: bool | None = None,
    retrieval: RetrievalService = Depends(get_retrieval_service),
    generation: GenerationService = Depends(get_generation_service),
    agent: QueryRouter | None = Depends(get_query_router),
    web_tool: WebSearchTool | None = Depends(get_web_search_tool),
) -> QueryResponse:
    decision = _decide(request.question, agent)
    surfaced_route = decision.route if agent is not None else None

    # Clarify: answer with the follow-up question, no retrieval.
    if decision.route == ROUTE_CLARIFY:
        return QueryResponse(
            answer=decision.clarification or _CLARIFY_FALLBACK,
            citations=[],
            route=ROUTE_CLARIFY,
        )

    # Web search: only if the tool is enabled; otherwise fall through to docs.
    if decision.route == ROUTE_WEB and web_tool is not None:
        results = web_tool.search(request.question)
        answer = generation.generate_web_answer(request.question, results)
        return QueryResponse(
            answer=answer, citations=[], route=ROUTE_WEB, web_sources=_to_web_sources(results)
        )

    # Answer from docs (the default, and the fallback when web is unavailable).
    hits = retrieval.retrieve(
        request.question, top_k=request.top_k, use_hybrid=use_hybrid, use_rerank=use_rerank
    )
    answer = generation.generate_answer(request.question, [h.chunk for h in hits])
    citations = [Citation(**c) for c in build_citations(hits)]
    effective = ROUTE_ANSWER if surfaced_route == ROUTE_WEB else surfaced_route
    return QueryResponse(answer=answer, citations=citations, route=effective)


@router.post("/query/stream")
def query_stream(
    request: QueryRequest,
    use_hybrid: bool | None = None,
    use_rerank: bool | None = None,
    retrieval: RetrievalService = Depends(get_retrieval_service),
    generation: GenerationService = Depends(get_generation_service),
    agent: QueryRouter | None = Depends(get_query_router),
    web_tool: WebSearchTool | None = Depends(get_web_search_tool),
) -> EventSourceResponse:
    """Streaming variant of /query (SSE): `token` events, then `citations`, then
    `done` (or an `error` event on mid-stream failure). The agent branches the
    same way as /query — clarify streams the follow-up; web_search streams a
    web-grounded answer."""
    decision = _decide(request.question, agent)

    # Clarify: stream the single follow-up line, no retrieval/citations.
    if decision.route == ROUTE_CLARIFY:
        def clarify_stream():
            yield {"event": "token", "data": decision.clarification or _CLARIFY_FALLBACK}
            yield {"event": "done", "data": ""}
        return EventSourceResponse(clarify_stream())

    # Web search: stream a web-grounded answer (citation chips omitted in the
    # stream; the non-stream /query returns full web_sources).
    if decision.route == ROUTE_WEB and web_tool is not None:
        def web_stream():
            try:
                results = web_tool.search(request.question)
                for delta in generation.generate_web_answer_stream(request.question, results):
                    yield {"event": "token", "data": delta}
            except Exception as exc:  # noqa: BLE001
                yield {"event": "error", "data": str(exc)}
                return
            yield {"event": "done", "data": ""}
        return EventSourceResponse(web_stream())

    # Answer from docs: retrieve up front (citations known), then stream.
    hits = retrieval.retrieve(
        request.question, top_k=request.top_k, use_hybrid=use_hybrid, use_rerank=use_rerank
    )
    citations = build_citations(hits)
    contexts = [h.chunk for h in hits]

    def event_stream():
        try:
            for delta in generation.generate_answer_stream(request.question, contexts):
                yield {"event": "token", "data": delta}
        except Exception as exc:  # noqa: BLE001 — surface upstream failures to the client
            yield {"event": "error", "data": str(exc)}
            return
        yield {"event": "citations", "data": json.dumps(citations)}
        yield {"event": "done", "data": ""}

    return EventSourceResponse(event_stream())
