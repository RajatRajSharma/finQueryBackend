"""EvaluationService — runs the test questions through the real pipeline and
scores the results (Week 3, see docs/finQueryEvaluation.md).

Flow: load the hand-written {question, ground_truth} set -> for each, run the
SAME retrieval + generation the API uses (capturing the answer + the contexts it
was grounded in) -> hand the batch to an Evaluator (RAGAS) -> cache + return the
report. Depends only on interfaces/services, so it's testable with fakes.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from app.core.domain import EvalRecord, EvalReport
from app.core.interfaces import Evaluator
from app.services.generation import GenerationService
from app.services.retrieval import RetrievalService


class EvaluationService:
    def __init__(
        self,
        retrieval: RetrievalService,
        generation: GenerationService,
        evaluator: Evaluator,
        questions_path: str,
        results_path: str,
        sample_size: int = 0,
    ) -> None:
        self._retrieval = retrieval
        self._generation = generation
        self._evaluator = evaluator
        self._questions_path = Path(questions_path)
        self._results_path = Path(results_path)
        self._sample_size = sample_size

    def _load_questions(self) -> list[dict]:
        if not self._questions_path.exists():
            raise FileNotFoundError(
                f"Eval question set not found at {self._questions_path}"
            )
        data = json.loads(self._questions_path.read_text(encoding="utf-8"))
        return data[: self._sample_size] if self._sample_size else data

    def _build_record(self, question: str, ground_truth: str) -> EvalRecord:
        """Run one question through the live pipeline, capturing what it produced."""
        hits = self._retrieval.retrieve(question)
        contexts = [h.chunk.text for h in hits]
        answer = self._generation.generate_answer(question, [h.chunk for h in hits])
        return EvalRecord(
            question=question, answer=answer, contexts=contexts, ground_truth=ground_truth
        )

    def run(self) -> EvalReport:
        questions = self._load_questions()
        records = [
            self._build_record(q["question"], q["ground_truth"]) for q in questions
        ]
        report = self._evaluator.evaluate(records)
        self._cache(report)
        return report

    def cached(self) -> EvalReport | None:
        """The last run's report, if one was saved — so GET /evals is instant and
        doesn't re-burn API calls on every request."""
        if not self._results_path.exists():
            return None
        data = json.loads(self._results_path.read_text(encoding="utf-8"))
        return EvalReport(**data)

    def _cache(self, report: EvalReport) -> None:
        self._results_path.parent.mkdir(parents=True, exist_ok=True)
        self._results_path.write_text(json.dumps(asdict(report), indent=2), encoding="utf-8")
