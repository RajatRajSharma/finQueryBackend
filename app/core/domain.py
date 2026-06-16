"""Internal domain models — the shared vocabulary of the RAG pipeline.

These are deliberately separate from the API schemas in app/models/schemas.py
(which describe the HTTP boundary). Domain models flow *between* components
(parser -> chunker -> embedder -> vector store); schemas flow *over the wire*.
Keeping them apart means the API can evolve without disturbing the engine,
and vice-versa (Single Responsibility / stable core).
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ParsedPage:
    """One page of extracted text from a source document."""

    source_file: str        # e.g. "AppleInc.pdf"
    page_number: int        # 1-based, preserved so citations can point at a page
    text: str


@dataclass
class Chunk:
    """A retrievable unit: a slice of a page, plus everything needed for
    storage, citation, and (optionally) its embedding vector."""

    chunk_id: str           # stable, deterministic id -> idempotent re-ingest
    text: str
    source_file: str
    company: str
    page_number: int
    embedding: list[float] | None = None
    metadata: dict = field(default_factory=dict)


@dataclass
class SearchHit:
    """A chunk returned by retrieval, with its relevance score (used in Day 3)."""

    chunk: Chunk
    score: float


@dataclass
class IngestionResult:
    """Outcome of ingesting one document — returned up to the API layer."""

    source_file: str
    company: str
    pages_parsed: int
    chunks_created: int
    chunks_stored: int


# --- Week 3: agentic routing ---

# The three ways the agent can handle a question (see services/agent.py).
ROUTE_ANSWER = "answer_from_docs"   # answer from the uploaded reports (the default)
ROUTE_CLARIFY = "clarify"           # too vague — ask the user a follow-up
ROUTE_WEB = "web_search"            # not in the docs — fall back to web search


@dataclass(frozen=True)
class RouteDecision:
    """The agent router's verdict on how to handle a question."""

    route: str                       # one of the ROUTE_* constants above
    clarification: str | None = None  # a follow-up question when route == clarify
    reason: str | None = None         # short rationale (useful for debugging/logging)


@dataclass(frozen=True)
class WebResult:
    """One result from the web-search fallback tool (Week 3)."""

    title: str
    url: str
    snippet: str


# --- Week 3: RAGAS evaluation ---


@dataclass
class EvalRecord:
    """One graded sample: a test question, what the pipeline produced for it,
    and the known-correct answer. Fed to the Evaluator (RAGAS)."""

    question: str
    answer: str                 # the pipeline's answer
    contexts: list[str]         # the retrieved chunk texts (what RAGAS scores against)
    ground_truth: str           # hand-written correct answer
    sources: list[dict] = field(default_factory=list)  # {doc, page, snippet} for display


@dataclass
class EvalReport:
    """Raw evaluator output: averaged metrics + per-question metric scores."""

    metrics: dict[str, float]            # averaged scores, e.g. {"faithfulness": 0.93, ...}
    per_question: list[dict]             # one row per question: its metrics (+ the question)
    num_questions: int


@dataclass
class EvalRun:
    """The full, UI-facing evaluation result (cached + returned by GET /evals).

    Built by EvaluationService by merging the evaluator's scores with each
    record's answer/ground-truth/sources, plus run metadata, the pipeline config
    used, and an optional baseline to show the before/after improvement."""

    run_id: str
    created_at: str                      # ISO-8601 UTC
    question_count: int
    metrics: dict[str, float]            # camelCase, e.g. {"faithfulness": .94, "answerRelevancy": .91}
    config: dict                         # {model, embeddingModel, reranker, hybrid, topK}
    questions: list[dict]                # per-question: scores + answer + groundTruth + retrievedContexts
    baseline: dict | None = None         # camelCase metrics of the saved reference run, if any
