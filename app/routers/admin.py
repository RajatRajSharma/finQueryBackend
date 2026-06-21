"""Admin router — destructive maintenance ops, behind a token guard.

POST /admin/prune deletes every stored chunk whose document isn't in the
keep-list (the PDFs in data/raw/). API fallback for scripts/prune_corpus.py,
sharing the same CorpusPruner service.

Safety:
  - Disabled unless ADMIN_API_KEY is set (returns 503 otherwise).
  - Requires the matching `X-Admin-Token` header (401 on mismatch).
  - Dry run by default: nothing is deleted unless `?apply=true` is passed.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException

from app.config import settings
from app.core.factory import get_corpus_pruner
from app.models.schemas import PruneResponse
from app.services.maintenance import CorpusPruner

router = APIRouter(prefix="/admin", tags=["admin"])


def _require_admin(x_admin_token: str | None = Header(default=None)) -> None:
    """Gate every admin route on the shared secret in ADMIN_API_KEY."""
    if not settings.ADMIN_API_KEY:
        raise HTTPException(
            status_code=503,
            detail="Admin API is disabled. Set ADMIN_API_KEY to enable it.",
        )
    if x_admin_token != settings.ADMIN_API_KEY:
        raise HTTPException(status_code=401, detail="Invalid or missing X-Admin-Token.")


@router.post(
    "/prune",
    response_model=PruneResponse,
    dependencies=[Depends(_require_admin)],
)
def prune(
    apply: bool = False,
    pruner: CorpusPruner = Depends(get_corpus_pruner),
) -> PruneResponse:
    """Prune the store to the data/raw keep-list.

    Dry run by default (`applied=false`, nothing deleted). Pass `?apply=true` to
    actually delete the out-of-keep-list chunks.
    """
    result = pruner.prune(apply=apply)
    return PruneResponse(
        applied=result.applied,
        keep=result.keep,
        kept_counts=result.kept_counts,
        deleted_counts=result.deleted_counts,
        deleted_total=result.deleted_total,
    )
