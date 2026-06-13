"""Health router — liveness + readiness, split out of main.py.

Two distinct concerns, two endpoints (this is the "properly divided" health
API):
  - GET /health        liveness  — is the process up? (no dependencies touched)
  - GET /health/ready  readiness — are downstream deps (Qdrant) reachable?

Liveness is what a container orchestrator restarts on; readiness is what a load
balancer uses to decide whether to send traffic. Keeping them separate is the
standard production pattern and scales cleanly as more dependencies are added
(just extend the `dependencies` map).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.config import settings
from app.core.factory import get_vector_store
from app.core.interfaces import VectorStore
from app.models.schemas import HealthResponse, ReadinessResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
def liveness() -> HealthResponse:
    """Process is up. Intentionally touches no external service."""
    return HealthResponse(status="ok", service="finquery-backend", version="0.1.0")


@router.get("/health/ready", response_model=ReadinessResponse)
def readiness(store: VectorStore = Depends(get_vector_store)) -> ReadinessResponse:
    """Reports whether downstream dependencies are reachable."""
    dependencies = {"qdrant": store.health_check()}
    status = "ready" if all(dependencies.values()) else "degraded"
    return ReadinessResponse(status=status, dependencies=dependencies)
