"""Composition root — the single place where concrete vendors are chosen.

Services ask for an interface (Embedder, VectorStore, ...) and get back whatever
the .env provider settings select. Builders are lru_cached so connections/clients
are reused process-wide instead of rebuilt per request.
"""

from __future__ import annotations

from functools import lru_cache

from app.clients.gemini_client import GeminiEmbedder, GeminiKeyPool, GeminiLLM
from app.clients.qdrant_client import QdrantVectorStore
from app.config import settings
from app.core.interfaces import (
    Chunker,
    DocumentParser,
    Embedder,
    Evaluator,
    LLMProvider,
    QueryRouter,
    Reranker,
    SparseRetriever,
    VectorStore,
    WebSearchTool,
)
from app.processing.chunker import SentenceChunker
from app.processing.pdf_parser import PyPdfParser
from app.services.generation import GenerationService
from app.services.evaluation import EvaluationService
from app.services.ingestion import IngestionService
from app.services.retrieval import RetrievalService


@lru_cache
def get_gemini_pool() -> GeminiKeyPool:
    """Shared Gemini key pool (rotates 1 -> 2 -> 3 on quota), used by both
    embedding and generation."""
    return GeminiKeyPool(settings.gemini_api_keys())


@lru_cache
def get_embedder() -> Embedder:
    provider = settings.EMBED_PROVIDER.lower()
    if provider == "gemini":
        return GeminiEmbedder(
            pool=get_gemini_pool(),
            model=settings.EMBED_MODEL,
            dimension=settings.EMBED_DIM,
        )
    # if provider == "openai":
    #     from app.clients.openai_client import OpenAIEmbedder
    #     return OpenAIEmbedder(settings.OPENAI_API_KEY, settings.EMBED_MODEL, settings.EMBED_DIM)
    raise ValueError(f"Unsupported EMBED_PROVIDER: {settings.EMBED_PROVIDER!r}")


@lru_cache
def get_llm() -> LLMProvider:
    provider = settings.LLM_PROVIDER.lower()
    if provider == "gemini":
        return GeminiLLM(pool=get_gemini_pool(), model=settings.LLM_MODEL)
    # if provider == "openai":
    #     from app.clients.openai_client import OpenAILLM
    #     return OpenAILLM(settings.OPENAI_API_KEY, settings.LLM_MODEL)
    raise ValueError(f"Unsupported LLM_PROVIDER: {settings.LLM_PROVIDER!r}")


@lru_cache
def get_query_router() -> QueryRouter | None:
    """Agent router, or None when ENABLE_AGENT is off. Reuses the existing LLM."""
    if not settings.ENABLE_AGENT:
        return None
    from app.services.agent import LLMQueryRouter

    return LLMQueryRouter(llm=get_llm())


@lru_cache
def get_web_search_tool() -> WebSearchTool | None:
    """Web-search fallback, or None when ENABLE_WEB_SEARCH is off. Lazy-imports
    the provider SDK so it isn't a hard dependency of the normal path."""
    if not settings.ENABLE_WEB_SEARCH:
        return None
    provider = settings.WEB_SEARCH_PROVIDER.lower()
    if provider == "duckduckgo":
        from app.clients.websearch_client import DuckDuckGoSearch

        return DuckDuckGoSearch(max_results=settings.WEB_SEARCH_MAX_RESULTS)
    raise ValueError(f"Unsupported WEB_SEARCH_PROVIDER: {settings.WEB_SEARCH_PROVIDER!r}")


@lru_cache
def get_reranker() -> Reranker | None:
    """Cohere reranker when a COHERE_API_KEY is configured, else None. Built on
    key presence (not on ENABLE_RERANK) so a per-request `use_rerank=true` can
    turn it on; ENABLE_RERANK only sets the default. Errors if rerank is the
    default but no key is set. Lazy-imports the cohere SDK only when built."""
    if not settings.COHERE_API_KEY.strip():
        if settings.ENABLE_RERANK:
            raise ValueError(
                "ENABLE_RERANK=true but COHERE_API_KEY is empty - set it in .env "
                "(or ENABLE_RERANK=false)."
            )
        return None
    provider = settings.RERANK_PROVIDER.lower()
    if provider == "cohere":
        from app.clients.cohere_client import CohereReranker

        return CohereReranker(api_key=settings.COHERE_API_KEY, model=settings.RERANK_MODEL)
    raise ValueError(f"Unsupported RERANK_PROVIDER: {settings.RERANK_PROVIDER!r}")


@lru_cache
def get_sparse_retriever() -> SparseRetriever:
    """BM25 keyword retriever, indexed once from the current vector-store contents
    (freshness trade-off: see bm25_index.py). Built lazily on first use, not gated
    on ENABLE_HYBRID, so a per-request `use_hybrid=true` can turn it on even when
    hybrid is off by default; ENABLE_HYBRID only sets the default."""
    from app.clients.bm25_index import Bm25Retriever

    retriever = Bm25Retriever()
    retriever.index(get_vector_store().all_chunks())
    return retriever


@lru_cache
def get_vector_store() -> VectorStore:
    store = settings.VECTOR_STORE.lower()
    if store == "qdrant":
        return QdrantVectorStore(
            url=settings.QDRANT_URL,
            collection=settings.QDRANT_COLLECTION,
            api_key=settings.QDRANT_API_KEY,
        )
    raise ValueError(f"Unsupported VECTOR_STORE: {settings.VECTOR_STORE!r}")


def get_corpus_pruner() -> "CorpusPruner":
    """Assemble the corpus-prune service. Not cached — cheap to build and the
    raw dir can change between calls."""
    from pathlib import Path

    from app.services.maintenance import CorpusPruner

    return CorpusPruner(vector_store=get_vector_store(), raw_dir=Path("data/raw"))


@lru_cache
def get_parser() -> DocumentParser:
    return PyPdfParser()


@lru_cache
def get_chunker() -> Chunker:
    return SentenceChunker(
        chunk_size=settings.CHUNK_SIZE, chunk_overlap=settings.CHUNK_OVERLAP
    )


def get_ingestion_service() -> IngestionService:
    """Assemble the ingestion pipeline. Used as a FastAPI dependency."""
    return IngestionService(
        parser=get_parser(),
        chunker=get_chunker(),
        embedder=get_embedder(),
        vector_store=get_vector_store(),
    )


def get_retrieval_service() -> RetrievalService:
    """Assemble the retrieval step. The sparse/rerank stages are passed as lazy
    providers (built on first use), with ENABLE_HYBRID/ENABLE_RERANK as the
    defaults a per-request `use_hybrid`/`use_rerank` can override."""
    return RetrievalService(
        embedder=get_embedder(),
        vector_store=get_vector_store(),
        top_k=settings.TOP_K,
        reranker=get_reranker,
        sparse=get_sparse_retriever,
        candidates=settings.RETRIEVE_CANDIDATES,
        hybrid_alpha=settings.HYBRID_ALPHA,
        hybrid_default=settings.ENABLE_HYBRID,
        rerank_default=settings.ENABLE_RERANK,
    )


def get_generation_service() -> GenerationService:
    """Assemble the generation step (LLM provider)."""
    return GenerationService(llm=get_llm())


@lru_cache
def get_evaluator() -> Evaluator:
    """RAGAS evaluator. Lazy-imports ragas (and its heavy deps) only here, so
    it's required only when /evals is called."""
    provider = settings.EVAL_PROVIDER.lower()
    if provider == "ragas":
        from app.clients.ragas_evaluator import RagasEvaluator

        return RagasEvaluator(
            keys=settings.gemini_api_keys(),
            llm_model=settings.LLM_MODEL,
            embed_model=settings.EMBED_MODEL,
            llm_rpm=settings.EVAL_LLM_RPM,
            max_workers=settings.EVAL_MAX_WORKERS,
            timeout=settings.EVAL_TIMEOUT,
        )
    raise ValueError(f"Unsupported EVAL_PROVIDER: {settings.EVAL_PROVIDER!r}")


def get_evaluation_service() -> EvaluationService:
    """Assemble the evaluation runner (pipeline + evaluator + question set)."""
    return EvaluationService(
        retrieval=get_retrieval_service(),
        generation=get_generation_service(),
        evaluator=get_evaluator(),
        questions_path=settings.EVAL_QUESTIONS_PATH,
        results_path=settings.EVAL_RESULTS_PATH,
        baseline_path=settings.EVAL_BASELINE_PATH,
        run_config={
            "model": settings.LLM_MODEL,
            "embeddingModel": settings.EMBED_MODEL,
            "reranker": settings.ENABLE_RERANK,
            "hybrid": settings.ENABLE_HYBRID,
            "topK": settings.TOP_K,
        },
        ttl_hours=settings.EVAL_CACHE_TTL_HOURS,
        sample_size=settings.EVAL_SAMPLE_SIZE,
    )
