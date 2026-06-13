"""Query router — POST /query (retrieve -> generate -> cite).

Thin orchestration over three injected services. Note the router doesn't know
about Gemini or Qdrant — it composes RetrievalService + GenerationService +
the citations helper, all resolved from the factory. Week 1 returns the full
answer in one response; SSE token streaming is added in Week 2.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

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
