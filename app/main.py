"""FinQuery backend — FastAPI app entry point.

Middleware + router registration only; no business logic or endpoints here.
"""

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.core.errors import ConfigurationError, UpstreamServiceError
from app.routers import admin, evals, health, query, upload

app = FastAPI(title="FinQuery API", version="0.1.1")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.FRONTEND_ORIGIN],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(ConfigurationError)
async def _configuration_error_handler(
    request: Request, exc: ConfigurationError
) -> JSONResponse:
    """Missing/invalid config -> 503, never a raw 500.

    Also catches errors raised during dependency construction (before the
    endpoint body runs)."""
    return JSONResponse(status_code=503, content={"detail": str(exc)})


@app.exception_handler(UpstreamServiceError)
async def _upstream_service_error_handler(
    request: Request, exc: UpstreamServiceError
) -> JSONResponse:
    """Transient vendor (Gemini) failure -> 503, not a raw 500. The service is
    up but a provider is momentarily unavailable (overload/rate-limit/timeout);
    clients can retry."""
    return JSONResponse(status_code=503, content={"detail": str(exc)})

# Mount routers.
app.include_router(health.router)
app.include_router(upload.router)
app.include_router(query.router)
app.include_router(evals.router)   # GET /evals (RAGAS scores)
app.include_router(admin.router)   # admin-only: POST /admin/prune (corpus cleanup)
