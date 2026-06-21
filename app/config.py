"""Central configuration for the FinQuery backend.

Settings load from environment variables (and .env in dev) via pydantic-settings.
Import the singleton `settings`; never read os.environ directly elsewhere.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- Provider selection (the only place to switch vendors; see factory.py) ---
    EMBED_PROVIDER: str = "gemini"
    LLM_PROVIDER: str = "gemini"
    VECTOR_STORE: str = "qdrant"

    # --- API keys (fill in .env) ---
    GEMINI_API_KEY: str = ""        # embeddings + generation
    # Extra free-tier keys (each its own project quota). Pool rotates 1 -> 2 -> 3
    # on quota exhaustion; leave blank if you only have one.
    GEMINI_API_KEY_2: str = ""
    GEMINI_API_KEY_3: str = ""
    OPENAI_API_KEY: str = ""        # only if you switch *_PROVIDER to openai
    COHERE_API_KEY: str = ""        # reranking

    # --- Qdrant vector DB ---
    # Local dev: Dockerized Qdrant, no auth (key empty). Prod: Cloud URL + key.
    QDRANT_URL: str = "http://localhost:6333"
    QDRANT_COLLECTION: str = "finquery_chunks"
    QDRANT_API_KEY: str = ""

    # --- Models + embedding dimension ---
    EMBED_MODEL: str = "gemini-embedding-001"  # Gemini embeddings (configurable dim)
    EMBED_DIM: int = 768                        # request 768-dim output (Qdrant size)
    LLM_MODEL: str = "gemini-2.5-flash"         # 2.0-flash has 0 free-tier quota on this key

    # --- Retrieval / chunking knobs ---
    CHUNK_SIZE: int = 512
    CHUNK_OVERLAP: int = 50
    TOP_K: int = 5                              # chunks fed to the LLM (final)

    # --- Reranking (Cohere) ---
    # When true, retrieval over-fetches RETRIEVE_CANDIDATES chunks and the
    # reranker keeps the best TOP_K. Off by default until COHERE_API_KEY is set.
    ENABLE_RERANK: bool = False
    RERANK_PROVIDER: str = "cohere"
    RERANK_MODEL: str = "rerank-english-v3.0"
    RETRIEVE_CANDIDATES: int = 20               # over-fetch pool before rerank

    # --- Hybrid retrieval (dense + BM25) ---
    ENABLE_HYBRID: bool = False
    HYBRID_ALPHA: float = 0.5                   # 1.0 = dense only, 0.0 = sparse only

    # --- Agentic routing + web-search fallback ---
    # ENABLE_AGENT routes each question (answer_from_docs | clarify | web_search)
    # before retrieving. Off by default.
    ENABLE_AGENT: bool = False
    # Web search is opt-in (core path must not depend on an external key).
    ENABLE_WEB_SEARCH: bool = False
    WEB_SEARCH_PROVIDER: str = "duckduckgo"     # duckduckgo (keyless) | tavily
    WEB_SEARCH_MAX_RESULTS: int = 5

    # --- RAGAS evaluation ---
    EVAL_PROVIDER: str = "ragas"                # ragas | fake (fake = no LLM, for CI/demo)
    EVAL_QUESTIONS_PATH: str = "data/eval/questions.json"
    EVAL_RESULTS_PATH: str = "data/eval/results.json"   # cached last run (gitignored)
    # Cap how many questions a run scores (0 = all). Keep small on the free tier.
    EVAL_SAMPLE_SIZE: int = 0
    # Throttle the RAGAS judge to live within the Gemini free-tier rate limit.
    # EVAL_LLM_RPM = max judge calls/minute (keep < the 20/min generate cap);
    # EVAL_MAX_WORKERS = 1 serializes jobs so they don't burst past the limit.
    EVAL_LLM_RPM: int = 12
    EVAL_MAX_WORKERS: int = 1
    EVAL_TIMEOUT: int = 300                     # per-job timeout (s); generous for serial + backoff
    # A real run is slow + quota-heavy, so GET /evals serves the last cached run
    # for this long before it's considered stale. 48h = 2 days; set 24, 1, etc.
    EVAL_CACHE_TTL_HOURS: float = 48.0
    EVAL_BASELINE_PATH: str = "data/eval/baseline.json"  # saved reference run for before/after

    # --- CORS: which frontend origin may call this API ---
    FRONTEND_ORIGIN: str = "http://localhost:5173"

    # --- Admin API (destructive maintenance ops, e.g. POST /admin/prune) ---
    # The admin endpoints are DISABLED until this is set. Once set, callers must
    # send it as the `X-Admin-Token` header. Keep it secret; set only in prod env.
    ADMIN_API_KEY: str = ""

    def gemini_api_keys(self) -> list[str]:
        """Non-empty Gemini keys in rotation order (1 -> 2 -> 3)."""
        return [
            k
            for k in (self.GEMINI_API_KEY, self.GEMINI_API_KEY_2, self.GEMINI_API_KEY_3)
            if k.strip()
        ]


# Singleton imported across the app.
settings = Settings()
