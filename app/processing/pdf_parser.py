"""PyPdfParser — extracts page text from a PDF using pypdf.

Implements the DocumentParser interface. Swapping to a different extraction
engine later (e.g. an OCR-backed parser for scanned filings, or unstructured.io
for better tables) means writing a sibling class here and pointing the factory
at it — IngestionService never changes.
"""

from __future__ import annotations

from pypdf import PdfReader

from app.core.domain import ParsedPage
from app.core.interfaces import DocumentParser


class PyPdfParser(DocumentParser):
    def parse(self, file_path: str, source_name: str) -> list[ParsedPage]:
        reader = PdfReader(file_path)
        pages: list[ParsedPage] = []
        for index, page in enumerate(reader.pages, start=1):
            text = (page.extract_text() or "").strip()
            if not text:
                continue  # skip blank / image-only pages (no OCR in Week 1)
            pages.append(
                ParsedPage(source_file=source_name, page_number=index, text=text)
            )
        return pages
