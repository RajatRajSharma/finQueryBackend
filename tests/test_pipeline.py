"""Pipeline tests that run with zero infrastructure (no Qdrant, no API key).

Proves the ingestion + query pipelines are wired correctly by driving the real
services with fake interface implementations. When Qdrant + Gemini are swapped
back in via the factory, the exact same orchestration runs unchanged.
"""

from __future__ import annotations

import json

from fastapi.testclient import TestClient

from app.core.domain import (
    ROUTE_ANSWER,
    ROUTE_CLARIFY,
    ROUTE_WEB,
    Chunk,
    ParsedPage,
    RouteDecision,
    SearchHit,
    WebResult,
)
from app.core.factory import (
    get_generation_service,
    get_query_router,
    get_retrieval_service,
    get_web_search_tool,
)
from app.main import app
from app.services.agent import LLMQueryRouter
from app.services.citations import build_citations
from app.services.evaluation import EvaluationService
from app.services.generation import GenerationService, build_prompt
from app.services.ingestion import IngestionService
from app.services.retrieval import RetrievalService, fuse
from tests.fakes import (
    FakeChunker,
    FakeEmbedder,
    FakeEvaluator,
    FakeLLM,
    FakeParser,
    FakeQueryRouter,
    FakeReranker,
    FakeSparseRetriever,
    FakeVectorStore,
    FakeWebSearchTool,
)


class _JsonLLM(FakeLLM):
    """LLM stub that returns a fixed string (used to drive the router parser)."""

    def __init__(self, payload: str) -> None:
        super().__init__()
        self._payload = payload

    def generate(self, prompt: str) -> str:
        self.last_prompt = prompt
        return self._payload


def _docs_services():
    """A retrieval + generation service pair backed entirely by fakes."""
    store = FakeVectorStore()
    IngestionService(FakeParser(_PAGES), FakeChunker(), FakeEmbedder(), store).ingest_file(
        "ignored.pdf", "Amazon.pdf", "Amazon"
    )
    return RetrievalService(FakeEmbedder(), store, top_k=5), GenerationService(FakeLLM())


def _chunk(cid: str) -> Chunk:
    return Chunk(chunk_id=cid, text=cid, source_file="x.pdf", company="X", page_number=1)

_PAGES = [
    ParsedPage("Amazon.pdf", 1, "Net sales increased 12% to $574 billion."),
    ParsedPage("Amazon.pdf", 2, "Operating income was $36.9 billion."),
]

_PAGES_4 = [
    ParsedPage("Amazon.pdf", n, f"Page {n} content.") for n in range(1, 5)
]


def test_ingestion_embeds_and_stores_each_chunk():
    store = FakeVectorStore()
    service = IngestionService(FakeParser(_PAGES), FakeChunker(), FakeEmbedder(), store)

    result = service.ingest_file("ignored.pdf", "Amazon.pdf", "Amazon")

    assert result.pages_parsed == 2
    assert result.chunks_created == 2
    assert result.chunks_stored == 2
    # Collection was sized to the embedder's dimension (Dependency Inversion win).
    assert store.ensured_dimension == FakeEmbedder().dimension


def test_retrieval_embeds_query_and_returns_hits():
    store = FakeVectorStore()
    IngestionService(FakeParser(_PAGES), FakeChunker(), FakeEmbedder(), store).ingest_file(
        "ignored.pdf", "Amazon.pdf", "Amazon"
    )

    hits = RetrievalService(FakeEmbedder(), store, top_k=5).retrieve("revenue?")

    assert len(hits) == 2
    assert hits[0].chunk.source_file == "Amazon.pdf"


def test_reranker_overfetches_then_keeps_top_n_reordered():
    store = FakeVectorStore()
    IngestionService(FakeParser(_PAGES_4), FakeChunker(), FakeEmbedder(), store).ingest_file(
        "ignored.pdf", "Amazon.pdf", "Amazon"
    )
    reranker = FakeReranker()
    service = RetrievalService(
        FakeEmbedder(), store, top_k=2, reranker=reranker, candidates=4
    )

    hits = service.retrieve("anything")

    # Over-fetched the full candidate pool (4), not just top_k (2)...
    assert reranker.last_pool_size == 4
    # ...then kept exactly top_k, in the reranker's order (FakeReranker reverses,
    # so the last candidate is now first — proving the reorder took effect).
    assert len(hits) == 2
    assert hits[0].chunk.page_number == 4
    # Score came from the reranker, not the store's flat 1.0.
    assert hits[0].score == 1.0 and hits[1].score < hits[0].score


def test_fuse_promotes_chunks_strong_in_both_lists():
    a, b, c, d = _chunk("A"), _chunk("B"), _chunk("C"), _chunk("D")
    dense = [SearchHit(a, 1.0), SearchHit(b, 0.5), SearchHit(d, 0.0)]
    sparse = [SearchHit(b, 2.0), SearchHit(c, 1.0)]

    fused = fuse(dense, sparse, alpha=0.5)

    # B is strong in BOTH lists -> it should outrank A (strong in dense only).
    assert fused[0].chunk.chunk_id == "B"
    assert fused[1].chunk.chunk_id == "A"
    # Deduped by chunk_id (B appears in both inputs, once in output).
    assert [h.chunk.chunk_id for h in fused].count("B") == 1


def test_hybrid_retrieval_fuses_dense_and_sparse():
    store = FakeVectorStore()
    IngestionService(FakeParser(_PAGES_4), FakeChunker(), FakeEmbedder(), store).ingest_file(
        "ignored.pdf", "Amazon.pdf", "Amazon"
    )
    # Sparse side favours page 3 strongly.
    sparse = FakeSparseRetriever([SearchHit(_chunk("Amazon.pdf::p3::c0"), 9.0)])
    service = RetrievalService(
        FakeEmbedder(), store, top_k=2, sparse=sparse, candidates=4, hybrid_alpha=0.5
    )

    hits = service.retrieve("anything")

    assert len(hits) == 2  # fused pool trimmed to top_k


def test_prompt_includes_context_and_question():
    chunks = FakeChunker().chunk(_PAGES, "Amazon")
    prompt = build_prompt("What were net sales?", chunks)

    assert "Net sales increased 12%" in prompt
    assert "What were net sales?" in prompt
    assert "ONLY" in prompt  # grounding instruction present


def test_generation_passes_context_to_llm():
    llm = FakeLLM()
    chunks = FakeChunker().chunk(_PAGES, "Amazon")

    answer = GenerationService(llm).generate_answer("net sales?", chunks)

    assert answer == "FAKE_ANSWER"
    assert "Net sales increased 12%" in (llm.last_prompt or "")


def test_generation_streams_answer_in_deltas():
    llm = FakeLLM()
    chunks = FakeChunker().chunk(_PAGES, "Amazon")

    deltas = list(GenerationService(llm).generate_answer_stream("net sales?", chunks))

    # Streamed in pieces that concatenate to the full answer...
    assert len(deltas) > 1
    assert "".join(deltas) == "FAKE_ANSWER"
    # ...and the same grounding context reached the model.
    assert "Net sales increased 12%" in (llm.last_prompt or "")


def test_citations_map_back_to_source_and_page():
    store = FakeVectorStore()
    IngestionService(FakeParser(_PAGES), FakeChunker(), FakeEmbedder(), store).ingest_file(
        "ignored.pdf", "Amazon.pdf", "Amazon"
    )
    hits = RetrievalService(FakeEmbedder(), store, top_k=5).retrieve("revenue?")

    citations = build_citations(hits)

    assert citations[0]["source_file"] == "Amazon.pdf"
    assert citations[0]["page_number"] == 1
    assert "Net sales" in citations[0]["snippet"]


# --- Week 3: agent router + web-search fallback ---


def test_router_parses_clarify_route():
    llm = _JsonLLM('{"route": "clarify", "clarification": "Which company and metric?"}')
    decision = LLMQueryRouter(llm).route("how did they do?")
    assert decision.route == ROUTE_CLARIFY
    assert "Which company" in (decision.clarification or "")


def test_router_falls_back_to_docs_on_unparseable_reply():
    # FakeLLM returns "FAKE_ANSWER" (not JSON) -> safe default, never crashes.
    decision = LLMQueryRouter(FakeLLM()).route("anything")
    assert decision.route == ROUTE_ANSWER


def _const(val):
    # No-arg provider: FastAPI introspects the override's signature, so it must
    # take NO parameters (a `lambda v=val: v` would make FastAPI treat `v` as an
    # injectable param). The closure binds `val` per call, avoiding late binding.
    return lambda: val


def _override(mapping):
    # Keyed by the dependency FUNCTION object (FastAPI matches on identity).
    for dep, val in mapping.items():
        app.dependency_overrides[dep] = _const(val)


def test_query_clarify_branch_returns_followup_without_retrieval():
    retrieval, generation = _docs_services()
    _override({
        get_query_router: FakeQueryRouter(RouteDecision(ROUTE_CLARIFY, clarification="Which company?")),
        get_web_search_tool: None,
        get_retrieval_service: retrieval,
        get_generation_service: generation,
    })
    try:
        body = TestClient(app).post("/query", json={"question": "how did they do?"}).json()
    finally:
        app.dependency_overrides.clear()
    assert body["route"] == ROUTE_CLARIFY
    assert "Which company" in body["answer"]
    assert body["citations"] == []


def test_query_web_branch_uses_tool_and_returns_web_sources():
    retrieval, generation = _docs_services()
    tool = FakeWebSearchTool([WebResult(title="Reuters", url="http://r.com", snippet="news")])
    _override({
        get_query_router: FakeQueryRouter(RouteDecision(ROUTE_WEB)),
        get_web_search_tool: tool,
        get_retrieval_service: retrieval,
        get_generation_service: generation,
    })
    try:
        body = TestClient(app).post("/query", json={"question": "latest stock price?"}).json()
    finally:
        app.dependency_overrides.clear()
    assert body["route"] == ROUTE_WEB
    assert body["answer"] == "FAKE_ANSWER"
    assert body["web_sources"][0]["title"] == "Reuters"
    assert tool.last_query == "latest stock price?"


def test_query_docs_branch_when_agent_routes_to_answer():
    retrieval, generation = _docs_services()
    _override({
        get_query_router: FakeQueryRouter(RouteDecision(ROUTE_ANSWER)),
        get_web_search_tool: None,
        get_retrieval_service: retrieval,
        get_generation_service: generation,
    })
    try:
        body = TestClient(app).post("/query", json={"question": "net sales?"}).json()
    finally:
        app.dependency_overrides.clear()
    assert body["route"] == ROUTE_ANSWER
    assert body["answer"] == "FAKE_ANSWER"
    assert len(body["citations"]) > 0


def test_evaluation_service_runs_pipeline_scores_and_caches(tmp_path):
    store = FakeVectorStore()
    IngestionService(FakeParser(_PAGES), FakeChunker(), FakeEmbedder(), store).ingest_file(
        "ignored.pdf", "Amazon.pdf", "Amazon"
    )
    retrieval = RetrievalService(FakeEmbedder(), store, top_k=5)
    generation = GenerationService(FakeLLM())
    evaluator = FakeEvaluator()
    qpath = tmp_path / "questions.json"
    qpath.write_text(json.dumps([{"question": "net sales?", "ground_truth": "$574B"}]))
    rpath = tmp_path / "results.json"

    service = EvaluationService(retrieval, generation, evaluator, str(qpath), str(rpath))
    report = service.run()

    assert report.num_questions == 1
    # The pipeline actually ran: the evaluator got the generated answer + contexts.
    assert evaluator.seen[0].answer == "FAKE_ANSWER"
    assert evaluator.seen[0].contexts and "Net sales" in evaluator.seen[0].contexts[0]
    assert evaluator.seen[0].ground_truth == "$574B"
    # Result was cached and reloads.
    assert rpath.exists()
    assert service.cached().num_questions == 1
