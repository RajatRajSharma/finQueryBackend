"""Upload router — POST /upload (triggers ingestion).

Thin HTTP layer: validate, persist the file, hand off to the injected
IngestionService. No vendor SDK imported here.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from app.core.factory import get_ingestion_service
from app.models.schemas import IngestionResponse
from app.services.ingestion import IngestionService

router = APIRouter(tags=["ingestion"])

# Where uploaded PDFs are persisted (same place the seed corpus lives).
_RAW_DIR = Path("data/raw")


def _company_from_filename(filename: str) -> str:
    """Derive a display company name from the file stem (e.g. 'AppleInc')."""
    return Path(filename).stem


@router.post("/upload", response_model=IngestionResponse)
async def upload(
    file: UploadFile = File(...),
    service: IngestionService = Depends(get_ingestion_service),
) -> IngestionResponse:
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only .pdf files are accepted.")

    _RAW_DIR.mkdir(parents=True, exist_ok=True)
    destination = _RAW_DIR / file.filename
    destination.write_bytes(await file.read())

    # Config problems (e.g. missing API key) raise ConfigurationError, which the
    # app-level handler in main.py turns into a 503 — no try/except needed.
    result = service.ingest_file(
        file_path=str(destination),
        source_name=file.filename,
        company=_company_from_filename(file.filename),
    )

    return IngestionResponse(
        source_file=result.source_file,
        company=result.company,
        pages_parsed=result.pages_parsed,
        chunks_created=result.chunks_created,
        chunks_stored=result.chunks_stored,
    )
