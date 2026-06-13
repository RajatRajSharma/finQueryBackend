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
    TOP_K: int = 5

    # --- CORS: which frontend origin may call this API ---
    FRONTEND_ORIGIN: str = "http://localhost:5173"


# Singleton imported across the app.
settings = Settings()
