"""Central configuration for the FinQuery backend.

All settings load from environment variables (and the local .env file in dev)
via pydantic-settings. Import the singleton `settings` anywhere you need a
value — never read os.environ directly elsewhere.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- Provider selection (the ONLY place to switch vendors) ---
    # Swap "gemini" -> "openai" here (after adding the impl) and nothing
    # else in the codebase needs to change. See app/core/factory.py.
    EMBED_PROVIDER: str = "gemini"
    LLM_PROVIDER: str = "gemini"
    VECTOR_STORE: str = "qdrant"

    # --- API keys (fill in .env — empty for now) ---
    GEMINI_API_KEY: str = ""        # embeddings + generation (Week 1)
    OPENAI_API_KEY: str = ""        # only if you switch *_PROVIDER to openai
    COHERE_API_KEY: str = ""        # reranking (Week 2 — leave empty for now)

    # --- Qdrant vector DB ---
    QDRANT_URL: str = "http://localhost:6333"
    QDRANT_COLLECTION: str = "finquery_chunks"

    # --- Models + embedding dimension ---
    EMBED_MODEL: str = "gemini-embedding-001"  # Gemini embeddings (configurable dim)
    EMBED_DIM: int = 768                        # request 768-dim output (Qdrant size)
    LLM_MODEL: str = "gemini-2.5-flash"         # 2.0-flash has 0 free-tier quota on this key

    # --- Retrieval / chunking knobs ---
    CHUNK_SIZE: int = 512
    CHUNK_OVERLAP: int = 50
    TOP_K: int = 5                              # chunks fed to the LLM (final)

    # --- Week 2: reranking (Cohere) ---
    # When ENABLE_RERANK is true, retrieval over-fetches RETRIEVE_CANDIDATES
    # chunks and a reranker keeps the best TOP_K. Off by default so Week 1
    # behaviour is unchanged until COHERE_API_KEY is set.
    ENABLE_RERANK: bool = False
    RERANK_PROVIDER: str = "cohere"
    RERANK_MODEL: str = "rerank-english-v3.0"
    RETRIEVE_CANDIDATES: int = 20               # over-fetch pool before rerank

    # --- Week 2: hybrid retrieval (dense + BM25) ---
    ENABLE_HYBRID: bool = False
    HYBRID_ALPHA: float = 0.5                   # 1.0 = dense only, 0.0 = sparse only

    # --- CORS: which frontend origin may call this API ---
    FRONTEND_ORIGIN: str = "http://localhost:5173"


# Singleton imported across the app.
settings = Settings()
