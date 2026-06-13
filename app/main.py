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
from app.core.errors import ConfigurationError
from app.routers import health, query, upload

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

# Mount routers. The evals router gets added in Week 3.
app.include_router(health.router)
app.include_router(upload.router)
app.include_router(query.router)
