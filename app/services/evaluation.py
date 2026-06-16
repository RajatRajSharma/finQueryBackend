"""EvaluationService — runs the test questions through the real pipeline and
scores them (Week 3, see docs/finQueryEvaluation.md).

Flow: load the hand-written {question, ground_truth} set -> for each, run the
SAME retrieval + generation the API uses (capturing the answer + the contexts it
was grounded in) -> score the batch with an Evaluator (RAGAS) -> assemble a rich,
UI-facing EvalRun (run id, timestamp, camelCase metrics, the pipeline config, a
per-question breakdown with sources, and an optional baseline) -> cache it.

A real run is slow + quota-heavy, so GET /evals serves the cached run until it's
older than EVAL_CACHE_TTL_HOURS. Depends only on interfaces/services — testable
with fakes.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from app.core.domain import EvalRecord, EvalRun
from app.core.interfaces import Evaluator
from app.services.generation import GenerationService
from app.services.retrieval import RetrievalService

_SNIPPET_CHARS = 240

# RAGAS metric (snake_case) -> API (camelCase).
_CAMEL = {
    "faithfulness": "faithfulness",
    "answer_relevancy": "answerRelevancy",
    "context_precision": "contextPrecision",
    "context_recall": "contextRecall",
}


def _camel_metrics(scores: dict) -> dict:
    """Rename metric keys to camelCase; drop the 'question' label if present."""
    return {_CAMEL.get(k, k): v for k, v in scores.items() if k in _CAMEL}


class EvaluationService:
    def __init__(
        self,
        retrieval: RetrievalService,
        generation: GenerationService,
        evaluator: Evaluator,
        questions_path: str,
        results_path: str,
        baseline_path: str,
        run_config: dict,
        ttl_hours: float = 48.0,
        sample_size: int = 0,
    ) -> None:
        self._retrieval = retrieval
        self._generation = generation
        self._evaluator = evaluator
        self._questions_path = Path(questions_path)
        self._results_path = Path(results_path)
        self._baseline_path = Path(baseline_path)
        self._run_config = run_config
        self._ttl_hours = ttl_hours
        self._sample_size = sample_size

    # --- running an evaluation ---------------------------------------------

    def run(self, as_baseline: bool = False) -> EvalRun:
        questions = self._load_questions()
        records = [self._build_record(q["question"], q["ground_truth"]) for q in questions]
        report = self._evaluator.evaluate(records)

        # Merge evaluator scores (same order as records) with each record's
        # answer / ground truth / sources into the per-question breakdown.
        questions_out = []
        for record, scores in zip(records, report.per_question):
            entry = _camel_metrics(scores)
            entry["question"] = record.question
            entry["answer"] = record.answer
            entry["groundTruth"] = record.ground_truth
            entry["retrievedContexts"] = record.sources
            questions_out.append(entry)

        now = datetime.now(timezone.utc)
        run = EvalRun(
            run_id=f"eval_{now:%Y%m%d_%H%M%S}",
            created_at=now.isoformat(),
            question_count=report.num_questions,
            metrics=_camel_metrics(report.metrics),
            config=self._run_config,
            questions=questions_out,
            baseline=self._load_baseline() if not as_baseline else None,
        )
        self._write(self._results_path, asdict(run))
        if as_baseline:
            self._write(self._baseline_path, {"metrics": run.metrics, "createdAt": run.created_at})
        return run

    # --- cache + freshness --------------------------------------------------

    def cached(self) -> EvalRun | None:
        """The last run, if one was saved (so GET /evals is instant).

        Returns None for a missing OR malformed/old-format cache file, so a stale
        schema never 500s the endpoint — it just looks like "no run yet"."""
        if not self._results_path.exists():
            return None
        try:
            return EvalRun(**json.loads(self._results_path.read_text(encoding="utf-8")))
        except (ValueError, TypeError):
            return None

    def is_fresh(self, run: EvalRun) -> bool:
        """True if the cached run is within the TTL window."""
        try:
            age = datetime.now(timezone.utc) - datetime.fromisoformat(run.created_at)
        except (TypeError, ValueError):
            return False
        return age.total_seconds() <= self._ttl_hours * 3600

    # --- internals ----------------------------------------------------------

    def _load_questions(self) -> list[dict]:
        if not self._questions_path.exists():
            raise FileNotFoundError(f"Eval question set not found at {self._questions_path}")
        data = json.loads(self._questions_path.read_text(encoding="utf-8"))
        return data[: self._sample_size] if self._sample_size else data

    def _build_record(self, question: str, ground_truth: str) -> EvalRecord:
        """Run one question through the live pipeline, capturing what it produced."""
        hits = self._retrieval.retrieve(question)
        return EvalRecord(
            question=question,
            answer=self._generation.generate_answer(question, [h.chunk for h in hits]),
            contexts=[h.chunk.text for h in hits],
            ground_truth=ground_truth,
            sources=[
                {
                    "doc": h.chunk.source_file,
                    "page": h.chunk.page_number,
                    "snippet": _snippet(h.chunk.text),
                }
                for h in hits
            ],
        )

    def _load_baseline(self) -> dict | None:
        if not self._baseline_path.exists():
            return None
        return json.loads(self._baseline_path.read_text(encoding="utf-8")).get("metrics")

    @staticmethod
    def _write(path: Path, data: dict) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _snippet(text: str) -> str:
    s = text.strip().replace("\n", " ")
    return s[:_SNIPPET_CHARS].rstrip() + "…" if len(s) > _SNIPPET_CHARS else s
