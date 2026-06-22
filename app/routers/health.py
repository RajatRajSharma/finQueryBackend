"""Health router — liveness + readiness.

  - GET /health        liveness  — is the process up? (touches no dependencies)
  - GET /health/ready  readiness — are downstream deps (Qdrant) reachable?

Liveness drives orchestrator restarts; readiness drives load-balancer traffic.
Add a dependency by extending the `dependencies` map.
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
    return HealthResponse(status="ok", service="finquery-backend", version="0.1.1")


@router.get("/health/ready", response_model=ReadinessResponse)
def readiness(store: VectorStore = Depends(get_vector_store)) -> ReadinessResponse:
    """Reports whether downstream dependencies are reachable."""
    dependencies = {"qdrant": store.health_check()}
    status = "ready" if all(dependencies.values()) else "degraded"
    return ReadinessResponse(status=status, dependencies=dependencies)
