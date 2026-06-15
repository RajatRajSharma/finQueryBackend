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

from app.clients.gemini_client import GeminiEmbedder, GeminiLLM
from app.clients.qdrant_client import QdrantVectorStore
from app.config import settings
from app.core.interfaces import (
    Chunker,
    DocumentParser,
    Embedder,
    LLMProvider,
    Reranker,
    VectorStore,
)
from app.processing.chunker import SentenceChunker
from app.processing.pdf_parser import PyPdfParser
from app.services.generation import GenerationService
from app.services.ingestion import IngestionService
from app.services.retrieval import RetrievalService


@lru_cache
def get_embedder() -> Embedder:
    provider = settings.EMBED_PROVIDER.lower()
    if provider == "gemini":
        return GeminiEmbedder(
            api_key=settings.GEMINI_API_KEY,
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
        return GeminiLLM(api_key=settings.GEMINI_API_KEY, model=settings.LLM_MODEL)
    # if provider == "openai":
    #     from app.clients.openai_client import OpenAILLM
    #     return OpenAILLM(settings.OPENAI_API_KEY, settings.LLM_MODEL)
    raise ValueError(f"Unsupported LLM_PROVIDER: {settings.LLM_PROVIDER!r}")


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
def get_vector_store() -> VectorStore:
    store = settings.VECTOR_STORE.lower()
    if store == "qdrant":
        return QdrantVectorStore(
            url=settings.QDRANT_URL, collection=settings.QDRANT_COLLECTION
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
        candidates=settings.RETRIEVE_CANDIDATES,
    )


def get_generation_service() -> GenerationService:
    """Assemble the generation step (LLM provider)."""
    return GenerationService(llm=get_llm())
