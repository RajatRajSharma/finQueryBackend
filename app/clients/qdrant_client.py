"""QdrantVectorStore — stores and searches chunk embeddings in Qdrant.

Implements the VectorStore interface and is the ONLY file that imports the
qdrant-client SDK. Swapping to pgvector/Weaviate/Pinecone later = one new
class satisfying VectorStore + one line in factory.py.

Qdrant point IDs must be UUIDs or unsigned ints, but our chunk_ids are readable
strings ("AppleInc.pdf::p42::c1"). We derive a deterministic UUIDv5 from the
chunk_id so re-ingesting the same chunk overwrites the same point (idempotent),
while keeping the human-readable id in the payload for citations.
"""

from __future__ import annotations

import uuid

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams

from app.core.domain import Chunk, SearchHit
from app.core.interfaces import VectorStore


def _point_id(chunk_id: str) -> str:
    """Stable UUID derived from the readable chunk id (idempotent upserts)."""
    return str(uuid.uuid5(uuid.NAMESPACE_URL, chunk_id))


class QdrantVectorStore(VectorStore):
    def __init__(self, url: str, collection: str) -> None:
        self._client = QdrantClient(url=url)
        self._collection = collection

    def ensure_collection(self, dimension: int) -> None:
        if not self._client.collection_exists(self._collection):
            self._client.create_collection(
                collection_name=self._collection,
                vectors_config=VectorParams(size=dimension, distance=Distance.COSINE),
            )

    def upsert(self, chunks: list[Chunk]) -> int:
        points = [
            PointStruct(
                id=_point_id(chunk.chunk_id),
                vector=chunk.embedding,
                payload={
                    "chunk_id": chunk.chunk_id,
                    "text": chunk.text,
                    "source_file": chunk.source_file,
                    "company": chunk.company,
                    "page_number": chunk.page_number,
                },
            )
            for chunk in chunks
            if chunk.embedding is not None
        ]
        if not points:
            return 0
        self._client.upsert(collection_name=self._collection, points=points)
        return len(points)

    def search(self, embedding: list[float], top_k: int) -> list[SearchHit]:
        result = self._client.query_points(
            collection_name=self._collection,
            query=embedding,
            limit=top_k,
            with_payload=True,
        )
        hits: list[SearchHit] = []
        for point in result.points:
            payload = point.payload or {}
            hits.append(
                SearchHit(
                    chunk=Chunk(
                        chunk_id=payload.get("chunk_id", str(point.id)),
                        text=payload.get("text", ""),
                        source_file=payload.get("source_file", ""),
                        company=payload.get("company", ""),
                        page_number=payload.get("page_number", 0),
                    ),
                    score=point.score,
                )
            )
        return hits

    def health_check(self) -> bool:
        try:
            self._client.get_collections()
            return True
        except Exception:
            return False
