"""RAGAS evaluator — the ONLY file that imports ragas / langchain-google-genai.

Scores answered questions on three RAGAS metrics using an LLM-as-judge:
  - faithfulness       : is the answer backed by the retrieved contexts?
  - answer_relevancy   : does the answer address the question?
  - context_precision  : did retrieval pull relevant chunks? (grades retrieval)

The judge + embeddings are pointed at **Gemini** (not RAGAS's default OpenAI) so
the project stays single-vendor. Everything is lazy-imported and only constructed
when EVAL_PROVIDER=ragas, so ragas isn't a hard dependency of the app.

Caveat (documented in docs/tuning.md): RAGAS makes several judge calls per question, so a
full run easily exceeds the Gemini free-tier rate limits — keep EVAL_SAMPLE_SIZE
small. Failures are translated to UpstreamServiceError -> HTTP 503.
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

from app.core.domain import EvalRecord, EvalReport
from app.core.errors import UpstreamServiceError
from app.core.interfaces import Evaluator

_METRIC_COLUMNS = [
    "faithfulness",
    "answer_relevancy",
    "context_precision",
    "context_recall",
]


@contextmanager
def _translate_ragas_errors() -> Iterator[None]:
    try:
        yield
    except Exception as exc:  # noqa: BLE001 — eval/LLM/transport failures → upstream
        raise UpstreamServiceError(
            f"RAGAS evaluation failed: {exc}. (Often the free-tier rate limit — "
            "lower EVAL_SAMPLE_SIZE and retry shortly.)"
        ) from exc


class RagasEvaluator(Evaluator):
    def __init__(
        self,
        keys: list[str],
        llm_model: str,
        embed_model: str,
        llm_rpm: int = 12,
        max_workers: int = 1,
        timeout: int = 300,
    ) -> None:
        if not keys:
            raise ConfigurationError("No Gemini API key for the RAGAS judge.")
        self._keys = keys
        self._llm_model = llm_model
        # langchain-google-genai expects a "models/..." embeddings id.
        self._embed_model = (
            embed_model if embed_model.startswith("models/") else f"models/{embed_model}"
        )
        self._llm_rpm = llm_rpm
        self._max_workers = max_workers
        self._timeout = timeout

    def evaluate(self, records: list[EvalRecord]) -> EvalReport:
        if not records:
            return EvalReport(metrics={}, per_question=[], num_questions=0)

        # Try each key in order. If a run comes back fully empty (every judge call
        # failed — i.e. that key is quota-exhausted), rotate to the next key.
        df = None
        for i, key in enumerate(self._keys):
            df = self._score(key, records)
            present = [m for m in _METRIC_COLUMNS if m in df.columns]
            has_any_score = any(df[m].notna().any() for m in present)
            if has_any_score or i == len(self._keys) - 1:
                break  # got scores, or this was the last key
        return _report_from_dataframe(df, [r.question for r in records])

    def _score(self, key: str, records: list[EvalRecord]):
        """Run RAGAS once with a single key; returns the per-row dataframe."""
        with _translate_ragas_errors():
            from langchain_core.rate_limiters import InMemoryRateLimiter
            from langchain_google_genai import (
                ChatGoogleGenerativeAI,
                GoogleGenerativeAIEmbeddings,
            )
            from ragas import EvaluationDataset, evaluate
            from ragas.dataset_schema import SingleTurnSample
            from ragas.embeddings import LangchainEmbeddingsWrapper
            from ragas.llms import LangchainLLMWrapper
            from ragas.metrics import (
                answer_relevancy,
                context_precision,
                context_recall,
                faithfulness,
            )
            from ragas.run_config import RunConfig

            # Throttle judge calls to stay under the Gemini free-tier rate limit:
            # a token-bucket limiter (requests/sec) + single-worker RunConfig so
            # RAGAS doesn't fire its metric jobs concurrently and burst the cap.
            rate_limiter = InMemoryRateLimiter(
                requests_per_second=max(self._llm_rpm, 1) / 60.0,
                check_every_n_seconds=0.5,
                max_bucket_size=1,
            )
            judge = LangchainLLMWrapper(
                ChatGoogleGenerativeAI(
                    model=self._llm_model, google_api_key=key, rate_limiter=rate_limiter
                )
            )
            embeddings = LangchainEmbeddingsWrapper(
                GoogleGenerativeAIEmbeddings(model=self._embed_model, google_api_key=key)
            )
            run_config = RunConfig(max_workers=self._max_workers, timeout=self._timeout)

            dataset = EvaluationDataset(
                samples=[
                    SingleTurnSample(
                        user_input=r.question,
                        response=r.answer,
                        retrieved_contexts=r.contexts,
                        reference=r.ground_truth,
                    )
                    for r in records
                ]
            )
            result = evaluate(
                dataset,
                metrics=[faithfulness, answer_relevancy, context_precision, context_recall],
                llm=judge,
                embeddings=embeddings,
                run_config=run_config,
            )
            return result.to_pandas()


def _report_from_dataframe(df, questions: list[str]) -> EvalReport:
    """Turn RAGAS's per-row dataframe into averaged metrics + per-question rows."""
    present = [m for m in _METRIC_COLUMNS if m in df.columns]
    metrics = {m: _safe_mean(df[m]) for m in present}
    per_question = []
    for i, row in df.iterrows():
        entry = {"question": questions[i] if i < len(questions) else row.get("user_input", "")}
        for m in present:
            entry[m] = _safe_float(row[m])
        per_question.append(entry)
    return EvalReport(metrics=metrics, per_question=per_question, num_questions=len(df))


def _safe_mean(series) -> float:
    clean = series.dropna()
    return round(float(clean.mean()), 4) if len(clean) else 0.0


def _safe_float(value) -> float:
    try:
        return round(float(value), 4)
    except (TypeError, ValueError):
        return 0.0
