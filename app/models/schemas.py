"""API schemas — the HTTP boundary contract (request/response shapes).

Pydantic models mirrored by src/types/index.ts (see finQueryArchitecture.md §8).
Decoupled from the internal domain models in app/core/domain.py so the wire
format and engine can change independently.
"""

from __future__ import annotations

from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str
    service: str
    version: str


class ReadinessResponse(BaseModel):
    status: str                      # "ready" | "degraded"
    dependencies: dict[str, bool]    # e.g. {"qdrant": true}


class IngestionResponse(BaseModel):
    source_file: str
    company: str
    pages_parsed: int
    chunks_created: int
    chunks_stored: int


class QueryRequest(BaseModel):
    question: str
    top_k: int | None = None     # optional override of the default top_k


class Citation(BaseModel):
    source_file: str
    company: str
    page_number: int
    snippet: str
    score: float


class WebSource(BaseModel):
    title: str
    url: str
    snippet: str


class QueryResponse(BaseModel):
    answer: str
    citations: list[Citation]
    # Which route handled this — "answer_from_docs" | "clarify" | "web_search".
    # None when the agent is disabled.
    route: str | None = None
    web_sources: list[WebSource] | None = None  # populated only on the web_search route


class PruneResponse(BaseModel):
    """Result of POST /admin/prune.

    `applied` is False on a dry run, True when the prune ran. `deleted_total`/
    `deleted_counts` count chunks outside the keep-list (deleted, or would-be on
    a dry run). `kept_counts` maps each keep-list document to its stored chunks."""

    applied: bool
    keep: list[str]
    kept_counts: dict[str, int]
    deleted_counts: dict[str, int]
    deleted_total: int


class EvalResponse(BaseModel):
    """UI-facing evaluation result (camelCase to match the frontend).

    `metrics`/`baseline` are metric maps (faithfulness, answerRelevancy,
    contextPrecision, contextRecall). `questions` rows mix per-question scores
    with answer/groundTruth/retrievedContexts."""

    runId: str
    createdAt: str
    questionCount: int
    metrics: dict[str, float]
    config: dict
    questions: list[dict]
    baseline: dict | None = None
    stale: bool = False              # cached run older than the TTL window
    running: bool = False            # a fresh run is currently in progress
