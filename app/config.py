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
    # Extra free-tier keys (each its own project quota). The pool rotates
    # 1 -> 2 -> 3 on quota exhaustion; leave blank if you only have one.
    GEMINI_API_KEY_2: str = ""
    GEMINI_API_KEY_3: str = ""
    OPENAI_API_KEY: str = ""        # only if you switch *_PROVIDER to openai
    COHERE_API_KEY: str = ""        # reranking (Week 2 — leave empty for now)

    # --- Qdrant vector DB ---
    # Local dev: Dockerized Qdrant on localhost, no auth (key empty).
    # Production: a Qdrant Cloud URL (https://...:6333) + its API key. The key
    # is optional so the local open instance keeps working with an empty value.
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

    # --- Week 3: agentic routing + web-search fallback ---
    # ENABLE_AGENT routes each question (answer_from_docs | clarify | web_search)
    # before retrieving. Off by default so /query stays the Week 2 pipeline.
    ENABLE_AGENT: bool = False
    # Web search is opt-in (the core demo must not depend on an external key).
    ENABLE_WEB_SEARCH: bool = False
    WEB_SEARCH_PROVIDER: str = "duckduckgo"     # duckduckgo (keyless) | tavily
    WEB_SEARCH_MAX_RESULTS: int = 5

    # --- Week 3: RAGAS evaluation ---
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

    def gemini_api_keys(self) -> list[str]:
        """Non-empty Gemini keys in rotation order (1 -> 2 -> 3)."""
        return [
            k
            for k in (self.GEMINI_API_KEY, self.GEMINI_API_KEY_2, self.GEMINI_API_KEY_3)
            if k.strip()
        ]


# Singleton imported across the app.
settings = Settings()
