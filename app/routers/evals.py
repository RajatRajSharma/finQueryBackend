"""Evals router — GET /evals (RAGAS quality scores).

Thin HTTP layer over EvaluationService. By default returns the last cached run
(instant, no API spend); pass ?run=true to execute a fresh evaluation through
the live pipeline. The heavy lifting (running questions + RAGAS scoring) lives
in the service; this router never imports ragas.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.core.factory import get_evaluation_service
from app.models.schemas import EvalResponse
from app.services.evaluation import EvaluationService

router = APIRouter(tags=["evaluation"])


@router.get("/evals", response_model=EvalResponse)
def evals(
    run: bool = False,
    service: EvaluationService = Depends(get_evaluation_service),
) -> EvalResponse:
    """Return RAGAS scores. `run=false` (default) serves the cached last run;
    `run=true` executes a fresh evaluation (slow + uses API quota)."""
    report = service.run() if run else service.cached()
    if report is None:
        raise HTTPException(
            status_code=404,
            detail="No cached evaluation yet. Call GET /evals?run=true to generate one.",
        )
    return EvalResponse(
        metrics=report.metrics,
        per_question=report.per_question,
        num_questions=report.num_questions,
    )
