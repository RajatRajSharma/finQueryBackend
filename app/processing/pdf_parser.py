"""PyPdfParser — extracts page text from a PDF using pypdf.

Implements the DocumentParser interface; a different engine (OCR, unstructured.io)
is a sibling class wired in via the factory.
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
                continue  # skip blank / image-only pages (no OCR)
            pages.append(
                ParsedPage(source_file=source_name, page_number=index, text=text)
            )
        return pages
