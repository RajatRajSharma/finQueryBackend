"""SentenceChunker — splits page text into ~token-sized chunks.

Implements the Chunker interface via LlamaIndex's SentenceSplitter (respects
sentence boundaries, adds overlap). Splits *per page* so each chunk retains its
page number for citations. LlamaIndex is contained to this file.
"""

from __future__ import annotations

from llama_index.core.node_parser import SentenceSplitter

from app.core.domain import Chunk, ParsedPage
from app.core.interfaces import Chunker


class SentenceChunker(Chunker):
    def __init__(self, chunk_size: int, chunk_overlap: int) -> None:
        self._splitter = SentenceSplitter(
            chunk_size=chunk_size, chunk_overlap=chunk_overlap
        )

    def chunk(self, pages: list[ParsedPage], company: str) -> list[Chunk]:
        chunks: list[Chunk] = []
        for page in pages:
            for position, piece in enumerate(self._splitter.split_text(page.text)):
                # Deterministic id: same file+page+position -> same id, so
                # re-ingesting a document overwrites instead of duplicating.
                chunk_id = f"{page.source_file}::p{page.page_number}::c{position}"
                chunks.append(
                    Chunk(
                        chunk_id=chunk_id,
                        text=piece,
                        source_file=page.source_file,
                        company=company,
                        page_number=page.page_number,
                    )
                )
        return chunks
