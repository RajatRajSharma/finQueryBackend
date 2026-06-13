"""IngestionService — orchestrates parse -> chunk -> embed -> store.

This is high-level policy. Notice it imports NO vendor: it depends only on the
abstract interfaces (DocumentParser, Chunker, Embedder, VectorStore) handed to
it via the constructor. That's Dependency Injection — the factory decides which
concrete Gemini/Qdrant/pypdf objects get wired in, so this class is testable
with fakes and indifferent to which vendor is behind each interface.

Maps 1:1 to the ingestion LLD in finQueryArchitecture.md §4.1.
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
        # 1-2. Parse PDF -> pages (with page numbers for citations).
        pages = self._parser.parse(file_path, source_name)

        # 3. Chunk each page.
        chunks = self._chunker.chunk(pages, company)

        # 4. Embed all chunk texts (batched inside the embedder).
        if chunks:
            vectors = self._embedder.embed_texts([c.text for c in chunks])
            for chunk, vector in zip(chunks, vectors):
                chunk.embedding = vector

        # 5. Store: make sure the collection exists, then upsert.
        self._store.ensure_collection(self._embedder.dimension)
        stored = self._store.upsert(chunks)

        return IngestionResult(
            source_file=source_name,
            company=company,
            pages_parsed=len(pages),
            chunks_created=len(chunks),
            chunks_stored=stored,
        )
