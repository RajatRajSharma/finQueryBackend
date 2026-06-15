"""Pipeline tests that run with zero infrastructure (no Qdrant, no API key).

Proves the ingestion + query pipelines are wired correctly by driving the real
services with fake interface implementations. When Qdrant + Gemini are swapped
back in via the factory, the exact same orchestration runs unchanged.
"""

from __future__ import annotations

from app.core.domain import ParsedPage
from app.services.citations import build_citations
from app.services.generation import GenerationService, build_prompt
from app.services.ingestion import IngestionService
from app.services.retrieval import RetrievalService
from tests.fakes import (
    FakeChunker,
    FakeEmbedder,
    FakeLLM,
    FakeParser,
    FakeReranker,
    FakeVectorStore,
)

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
