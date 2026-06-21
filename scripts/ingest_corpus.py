"""Batch-ingest every PDF in data/raw/ into the vector store.

Uses the same IngestionService + factory wiring as the API. Run from the repo
root (Qdrant up, GEMINI_API_KEY set):
    python -m scripts.ingest_corpus
"""

from __future__ import annotations

from pathlib import Path

from app.core.factory import get_ingestion_service

RAW_DIR = Path("data/raw")


def main() -> None:
    pdfs = sorted(RAW_DIR.glob("*.pdf"))
    if not pdfs:
        print(f"No PDFs found in {RAW_DIR}/ — add some and retry.")
        return

    service = get_ingestion_service()
    print(f"Ingesting {len(pdfs)} document(s) from {RAW_DIR}/\n")

    total_chunks = 0
    for pdf in pdfs:
        result = service.ingest_file(
            file_path=str(pdf),
            source_name=pdf.name,
            company=pdf.stem,
        )
        total_chunks += result.chunks_stored
        print(
            f"  {pdf.name:<20} "
            f"pages={result.pages_parsed:<4} "
            f"chunks={result.chunks_stored}"
        )

    print(f"\nDone. {total_chunks} chunks stored across {len(pdfs)} documents.")


if __name__ == "__main__":
    main()
