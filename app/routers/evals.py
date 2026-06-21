"""Evals router — RAGAS quality scores for the dashboard.

  - GET  /evals       → last cached run, with `stale`/`running` flags.
  - POST /evals/run   → kick off a fresh evaluation in the background,
                        optionally saving it as the baseline.

A run is throttled to the Gemini free-tier limit and can take minutes, so it
never blocks the request — the UI polls GET /evals until `running` clears.
EvaluationService does the work; this router never imports ragas.
"""

from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException

from app.core.factory import get_evaluation_service
from app.models.schemas import EvalResponse
from app.services.evaluation import EvaluationService

router = APIRouter(tags=["evaluation"])

# Single-flight guard: at most one background eval at a time (single-instance demo).
_run_state = {"running": False}


def _to_response(service: EvaluationService) -> EvalResponse:
    run = service.cached()
    if run is None:
        raise HTTPException(
            status_code=404,
            detail="No evaluation yet. POST /evals/run to generate one.",
        )
    return EvalResponse(
        runId=run.run_id,
        createdAt=run.created_at,
        questionCount=run.question_count,
        metrics=run.metrics,
        config=run.config,
        questions=run.questions,
        baseline=run.baseline,
        stale=not service.is_fresh(run),
        running=_run_state["running"],
    )


@router.get("/evals", response_model=EvalResponse)
def evals(service: EvaluationService = Depends(get_evaluation_service)) -> EvalResponse:
    """Return the last cached evaluation (fast). `stale=true` means it's older
    than the TTL — the UI can POST /evals/run to refresh."""
    return _to_response(service)


@router.post("/evals/run", status_code=202)
def evals_run(
    background_tasks: BackgroundTasks,
    as_baseline: bool = False,
    service: EvaluationService = Depends(get_evaluation_service),
) -> dict:
    """Trigger a fresh evaluation in the background. 409 if one is already running.
    `as_baseline=true` saves the run as the reference for before/after."""
    if _run_state["running"]:
        raise HTTPException(status_code=409, detail="An evaluation is already running.")

    def _job() -> None:
        try:
            service.run(as_baseline=as_baseline)
        finally:
            _run_state["running"] = False

    _run_state["running"] = True
    background_tasks.add_task(_job)
    return {"status": "started", "asBaseline": as_baseline}
