"""API schemas — the HTTP boundary contract (request/response shapes).

These Pydantic models are what the frontend sees and what src/types/index.ts
mirrors (see finQueryArchitecture.md §8). They are deliberately decoupled from
the internal domain models in app/core/domain.py: the wire format can change
without touching the engine, and the engine can change without breaking the API.
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


class QueryResponse(BaseModel):
    answer: str
    citations: list[Citation]
