"""IngestionService — orchestrates parse -> chunk -> embed -> store.

Depends only on the abstract interfaces (DocumentParser, Chunker, Embedder,
VectorStore); concrete vendors are injected by the factory.
"""

from __future__ import annotations

from app.core.domain import IngestionResult
from app.core.interfaces import Chunker, DocumentParser, Embedder, VectorStore


class IngestionService:
    def __init__(
        self,
        parser: DocumentParser,
        chunker: Chunker,
        embedder: Embedder,
        vector_store: VectorStore,
    ) -> None:
        self._parser = parser
        self._chunker = chunker
        self._embedder = embedder
        self._store = vector_store

    def ingest_file(
        self, file_path: str, source_name: str, company: str
    ) -> IngestionResult:
        # Parse PDF -> pages (page numbers retained for citations).
        pages = self._parser.parse(file_path, source_name)

        chunks = self._chunker.chunk(pages, company)

        # Embedder batches internally.
        if chunks:
            vectors = self._embedder.embed_texts([c.text for c in chunks])
            for chunk, vector in zip(chunks, vectors):
                chunk.embedding = vector

        # Ensure collection exists before upsert.
        self._store.ensure_collection(self._embedder.dimension)
        stored = self._store.upsert(chunks)

        return IngestionResult(
            source_file=source_name,
            company=company,
            pages_parsed=len(pages),
            chunks_created=len(chunks),
            chunks_stored=stored,
        )
