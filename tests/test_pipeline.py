"""Pipeline tests that run with zero infrastructure (no Qdrant, no API key).

Drive the real services with fake interface implementations; swapping in Qdrant
+ Gemini via the factory runs the same orchestration unchanged.
"""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient
from google.genai import errors as genai_errors

from app.clients.gemini_client import GeminiKeyPool
from app.core.errors import UpstreamServiceError

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
from app.config import settings
from app.core.factory import (
    get_corpus_pruner,
    get_evaluation_service,
    get_generation_service,
    get_query_router,
    get_retrieval_service,
    get_web_search_tool,
)
from app.main import app
from app.services.maintenance import CorpusPruner
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
    # Collection sized to the embedder's dimension.
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

    # Over-fetched the full candidate pool (4), not just top_k (2).
    assert reranker.last_pool_size == 4
    # Kept top_k in the reranker's order (FakeReranker reverses, so last is now first).
    assert len(hits) == 2
    assert hits[0].chunk.page_number == 4
    # Score came from the reranker, not the store's flat 1.0.
    assert hits[0].score == 1.0 and hits[1].score < hits[0].score


def test_fuse_promotes_chunks_strong_in_both_lists():
    a, b, c, d = _chunk("A"), _chunk("B"), _chunk("C"), _chunk("D")
    dense = [SearchHit(a, 1.0), SearchHit(b, 0.5), SearchHit(d, 0.0)]
    sparse = [SearchHit(b, 2.0), SearchHit(c, 1.0)]

    fused = fuse(dense, sparse, alpha=0.5)

    # B is strong in BOTH lists -> outranks A (strong in dense only).
    assert fused[0].chunk.chunk_id == "B"
    assert fused[1].chunk.chunk_id == "A"
    # Deduped by chunk_id (B in both inputs, once in output).
    assert [h.chunk.chunk_id for h in fused].count("B") == 1


def test_hybrid_retrieval_fuses_dense_and_sparse():
    store = FakeVectorStore()
    IngestionService(FakeParser(_PAGES_4), FakeChunker(), FakeEmbedder(), store).ingest_file(
        "ignored.pdf", "Amazon.pdf", "Amazon"
    )
    # Sparse side favours page 3.
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

    # Streamed in pieces that concatenate to the full answer.
    assert len(deltas) > 1
    assert "".join(deltas) == "FAKE_ANSWER"
    # Same grounding context reached the model.
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


# --- agent router + web-search fallback ---


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
    # No-arg provider: FastAPI introspects the override's signature, so a
    # `lambda v=val: v` would make it treat `v` as an injectable param.
    return lambda: val


def _override(mapping):
    # Keyed by the dependency function object (FastAPI matches on identity).
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


def _eval_service(tmp_path, sample_size=0):
    store = FakeVectorStore()
    IngestionService(FakeParser(_PAGES), FakeChunker(), FakeEmbedder(), store).ingest_file(
        "ignored.pdf", "Amazon.pdf", "Amazon"
    )
    qpath = tmp_path / "questions.json"
    qpath.write_text(json.dumps([{"question": "net sales?", "ground_truth": "$574B"}]))
    return EvaluationService(
        retrieval=RetrievalService(FakeEmbedder(), store, top_k=5),
        generation=GenerationService(FakeLLM()),
        evaluator=FakeEvaluator(),
        questions_path=str(qpath),
        results_path=str(tmp_path / "results.json"),
        baseline_path=str(tmp_path / "baseline.json"),
        run_config={"model": "gemini", "topK": 5},
        ttl_hours=48.0,
        sample_size=sample_size,
    )


def test_evaluation_service_builds_rich_run_and_caches(tmp_path):
    service = _eval_service(tmp_path)
    run = service.run()

    assert run.question_count == 1
    assert run.run_id.startswith("eval_") and run.created_at
    assert run.config["topK"] == 5
    # Per-question row merges pipeline output with source metadata.
    q0 = run.questions[0]
    assert q0["answer"] == "FAKE_ANSWER"
    assert q0["groundTruth"] == "$574B"
    assert q0["retrievedContexts"][0]["doc"] == "Amazon.pdf"
    assert "Net sales" in q0["retrievedContexts"][0]["snippet"]
    # Reloads from cache and is fresh within the TTL.
    cached = service.cached()
    assert cached.question_count == 1
    assert service.is_fresh(cached) is True


def test_evaluation_cached_ignores_malformed_or_old_format_file(tmp_path):
    service = _eval_service(tmp_path)
    # A malformed cache must not 500 the endpoint — treat as "no run".
    (tmp_path / "results.json").write_text(
        json.dumps({"metrics": {}, "per_question": [], "num_questions": 0})
    )
    assert service.cached() is None


def test_evaluation_cache_goes_stale_past_ttl(tmp_path):
    service = _eval_service(tmp_path)
    run = service.run()
    # An old timestamp should read as stale.
    run.created_at = "2000-01-01T00:00:00+00:00"
    assert service.is_fresh(run) is False


def test_evaluation_run_as_baseline_then_shows_in_next_run(tmp_path):
    service = _eval_service(tmp_path)
    service.run(as_baseline=True)        # saves baseline.json
    run = service.run()                  # next run picks it up
    assert run.baseline is not None
    assert "faithfulness" in run.baseline


def test_evals_endpoint_run_then_get(tmp_path):
    service = _eval_service(tmp_path)
    _override({get_evaluation_service: service})
    try:
        client = TestClient(app)
        # Nothing cached yet -> 404.
        assert client.get("/evals").status_code == 404
        # Trigger a background run; TestClient runs the task before returning.
        assert client.post("/evals/run").status_code == 202
        # Cached run comes back in camelCase, with per-question detail.
        body = client.get("/evals").json()
        assert body["runId"].startswith("eval_")
        assert body["questionCount"] == 1
        assert body["questions"][0]["answer"] == "FAKE_ANSWER"
        assert body["questions"][0]["retrievedContexts"][0]["doc"] == "Amazon.pdf"
        assert body["stale"] is False and body["running"] is False
    finally:
        app.dependency_overrides.clear()


# --- Gemini key-pool rotation (use all keys: 1 -> 2 -> 3 on quota) ---


def _quota_error():
    return genai_errors.APIError(429, {"error": {"message": "quota exhausted"}}, None)


def test_gemini_pool_rotates_to_next_key_on_quota():
    pool = GeminiKeyPool(["k1", "k2", "k3"])
    calls = {"n": 0}

    def call(_client):
        calls["n"] += 1
        if calls["n"] == 1:        # key 1 quota-exhausted
            raise _quota_error()
        return "ok-from-key-2"     # key 2 succeeds

    assert pool.run("test", call) == "ok-from-key-2"
    assert calls["n"] == 2         # rotated exactly once


def test_gemini_pool_raises_when_all_keys_exhausted():
    pool = GeminiKeyPool(["k1", "k2"])

    def call(_client):
        raise _quota_error()

    with pytest.raises(UpstreamServiceError):
        pool.run("test", call)


def test_gemini_pool_non_quota_error_is_not_rotated():
    pool = GeminiKeyPool(["k1", "k2"])
    calls = {"n": 0}

    def call(_client):
        calls["n"] += 1
        raise genai_errors.APIError(400, {"error": {"message": "bad request"}}, None)

    with pytest.raises(UpstreamServiceError):
        pool.run("test", call)
    assert calls["n"] == 1         # a 400 is fatal — don't waste other keys on it


# --- Corpus prune (maintenance service + admin endpoint) ---

def _doc_chunk(source_file: str, company: str = "X") -> Chunk:
    return Chunk(
        chunk_id=f"{source_file}::c1", text="t", source_file=source_file,
        company=company, page_number=1,
    )


def _pruner_with(tmp_path, keep_names, stored_sources):
    for name in keep_names:                       # keep-list = PDFs in the raw dir
        (tmp_path / name).write_bytes(b"%PDF-1.4")
    store = FakeVectorStore()
    store.upsert([_doc_chunk(src) for src in stored_sources])
    return CorpusPruner(vector_store=store, raw_dir=tmp_path), store


def test_prune_dry_run_reports_but_keeps_everything(tmp_path):
    pruner, store = _pruner_with(tmp_path, ["Apple.pdf"], ["Apple.pdf", "Junk.pdf", "Junk.pdf"])
    result = pruner.prune(apply=False)
    assert result.applied is False
    assert result.deleted_total == 2                # 2 Junk chunks would go
    assert result.deleted_counts == {"Junk.pdf": 2}
    assert result.kept_counts == {"Apple.pdf": 1}
    assert len(store.all_chunks()) == 3             # nothing actually deleted


def test_prune_apply_deletes_only_out_of_keeplist(tmp_path):
    pruner, store = _pruner_with(tmp_path, ["Apple.pdf"], ["Apple.pdf", "Junk.pdf", "Junk.pdf"])
    result = pruner.prune(apply=True)
    assert result.applied is True
    assert result.deleted_total == 2
    assert [c.source_file for c in store.all_chunks()] == ["Apple.pdf"]


def test_prune_refuses_empty_keeplist(tmp_path):
    pruner, _ = _pruner_with(tmp_path, [], ["Junk.pdf"])
    with pytest.raises(ValueError):
        pruner.prune(apply=True)                    # empty raw dir must never wipe all


def test_admin_prune_disabled_without_key(monkeypatch):
    monkeypatch.setattr(settings, "ADMIN_API_KEY", "")
    r = TestClient(app).post("/admin/prune")
    assert r.status_code == 503


def test_admin_prune_rejects_bad_token(monkeypatch):
    monkeypatch.setattr(settings, "ADMIN_API_KEY", "secret")
    r = TestClient(app).post("/admin/prune", headers={"X-Admin-Token": "wrong"})
    assert r.status_code == 401


def test_admin_prune_dry_run_with_valid_token(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "ADMIN_API_KEY", "secret")
    pruner, store = _pruner_with(tmp_path, ["Apple.pdf"], ["Apple.pdf", "Junk.pdf"])
    _override({get_corpus_pruner: pruner})
    try:
        r = TestClient(app).post("/admin/prune", headers={"X-Admin-Token": "secret"})
    finally:
        app.dependency_overrides.clear()
    assert r.status_code == 200
    body = r.json()
    assert body["applied"] is False and body["deleted_total"] == 1
    assert len(store.all_chunks()) == 2             # dry run deleted nothing
