"""Composition root — the single place where concrete vendors are chosen.

Every "which implementation?" decision lives here and nowhere else. Routers and
services ask the factory for an interface (Embedder, VectorStore, ...) and get
back whatever the .env provider settings select. This is what makes the swap
"change one line" real: to move embeddings to OpenAI you add an OpenAIEmbedder
class and one `elif` below — no service, router, or pipeline is edited.

Builders are cached (lru_cache) so the app reuses one Qdrant connection / one
Gemini client process-wide instead of rebuilding them per request.
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
    """One shared, rotating Gemini key pool (1 -> 2 -> 3 on quota) for the whole
    process, so embedding + generation draw from and rotate the same keys."""
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
    """The Week 3 agent router, or None when ENABLE_AGENT is off (then /query is
    the Week 2 pipeline). Reuses the existing LLM — no new vendor/key."""
    if not settings.ENABLE_AGENT:
        return None
    from app.services.agent import LLMQueryRouter

    return LLMQueryRouter(llm=get_llm())


@lru_cache
def get_web_search_tool() -> WebSearchTool | None:
    """The Week 3 web-search fallback, or None when ENABLE_WEB_SEARCH is off.

    Lazy-imports the provider SDK only when enabled, so `ddgs`/Tavily aren't hard
    dependencies of the normal path."""
    if not settings.ENABLE_WEB_SEARCH:
        return None
    provider = settings.WEB_SEARCH_PROVIDER.lower()
    if provider == "duckduckgo":
        from app.clients.websearch_client import DuckDuckGoSearch

        return DuckDuckGoSearch(max_results=settings.WEB_SEARCH_MAX_RESULTS)
    raise ValueError(f"Unsupported WEB_SEARCH_PROVIDER: {settings.WEB_SEARCH_PROVIDER!r}")


@lru_cache
def get_reranker() -> Reranker | None:
    """The Week 2 reranker, or None when disabled (then retrieval = Week 1).

    Returns None unless ENABLE_RERANK is true, so the cohere SDK is only
    imported (and a key only required) when reranking is actually switched on.
    """
    if not settings.ENABLE_RERANK:
        return None
    provider = settings.RERANK_PROVIDER.lower()
    if provider == "cohere":
        from app.clients.cohere_client import CohereReranker

        return CohereReranker(api_key=settings.COHERE_API_KEY, model=settings.RERANK_MODEL)
    raise ValueError(f"Unsupported RERANK_PROVIDER: {settings.RERANK_PROVIDER!r}")


@lru_cache
def get_sparse_retriever() -> SparseRetriever | None:
    """The Week 2 BM25 keyword retriever, or None when hybrid is disabled.

    Built once (lru_cache) and indexed from whatever is currently in the vector
    store, so the keyword half reuses the same corpus as dense search. See the
    freshness trade-off in bm25_index.py. When ENABLE_HYBRID is false this is
    None and retrieval stays dense-only.
    """
    if not settings.ENABLE_HYBRID:
        return None
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


@lru_cache
def get_parser() -> DocumentParser:
    return PyPdfParser()


@lru_cache
def get_chunker() -> Chunker:
    return SentenceChunker(
        chunk_size=settings.CHUNK_SIZE, chunk_overlap=settings.CHUNK_OVERLAP
    )


def get_ingestion_service() -> IngestionService:
    """Assemble the ingestion pipeline from its (interface-typed) parts.

    Used directly as a FastAPI dependency: `Depends(get_ingestion_service)`.
    """
    return IngestionService(
        parser=get_parser(),
        chunker=get_chunker(),
        embedder=get_embedder(),
        vector_store=get_vector_store(),
    )


def get_retrieval_service() -> RetrievalService:
    """Assemble the retrieval step (embedder + vector store + optional reranker).

    When ENABLE_RERANK is off, get_reranker() is None and this is exactly the
    Week 1 dense-only retriever.
    """
    return RetrievalService(
        embedder=get_embedder(),
        vector_store=get_vector_store(),
        top_k=settings.TOP_K,
        reranker=get_reranker(),
        sparse=get_sparse_retriever(),
        candidates=settings.RETRIEVE_CANDIDATES,
        hybrid_alpha=settings.HYBRID_ALPHA,
    )


def get_generation_service() -> GenerationService:
    """Assemble the generation step (LLM provider)."""
    return GenerationService(llm=get_llm())


@lru_cache
def get_evaluator() -> Evaluator:
    """The Week 3 RAGAS evaluator.

    Lazy-imports ragas only here, so it (and its heavy deps) aren't required for
    the normal app — only when /evals is actually called."""
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
