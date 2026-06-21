"""FinQuery backend — FastAPI app entry point.

Assembles the app: middleware + router registration only. No business logic
and no endpoints live here — each concern is a router under app/routers/ and
each piece of engine logic is a service/client behind an interface. Adding a
feature = add a router and include it below.
"""

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.core.errors import ConfigurationError, UpstreamServiceError
from app.routers import admin, evals, health, query, upload

app = FastAPI(title="FinQuery API", version="0.1.0")

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
    """Missing/invalid config -> 503 with a helpful message, never a raw 500.

    Catches the error wherever it's raised, including during dependency
    construction (which runs before the endpoint body)."""
    return JSONResponse(status_code=503, content={"detail": str(exc)})


@app.exception_handler(UpstreamServiceError)
async def _upstream_service_error_handler(
    request: Request, exc: UpstreamServiceError
) -> JSONResponse:
    """A vendor dependency (Gemini) failed transiently -> 503, not a raw 500.

    Keeps the contract honest: the service is up, but a provider it depends on
    is momentarily unavailable (overload/rate-limit/timeout). Clients can retry."""
    return JSONResponse(status_code=503, content={"detail": str(exc)})

# Mount routers.
app.include_router(health.router)
app.include_router(upload.router)
app.include_router(query.router)
app.include_router(evals.router)   # Week 3: GET /evals (RAGAS scores)
app.include_router(admin.router)   # admin-only: POST /admin/prune (corpus cleanup)
