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
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    MatchAny,
    PointStruct,
    VectorParams,
)

from app.core.domain import Chunk, SearchHit
from app.core.interfaces import VectorStore


def _point_id(chunk_id: str) -> str:
    """Stable UUID derived from the readable chunk id (idempotent upserts)."""
    return str(uuid.uuid5(uuid.NAMESPACE_URL, chunk_id))


class QdrantVectorStore(VectorStore):
    def __init__(self, url: str, collection: str, api_key: str | None = None) -> None:
        # api_key is None/empty for a local open instance, and set for an
        # authenticated production cluster (e.g. Qdrant Cloud over HTTPS).
        self._client = QdrantClient(url=url, api_key=api_key or None)
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

    def all_chunks(self) -> list[Chunk]:
        """Scroll the whole collection, returning chunks (payload only, no vectors).

        Used to build the BM25 keyword index. Pages through Qdrant in batches so
        it works for a large collection; vectors are skipped to keep it light.
        """
        if not self._client.collection_exists(self._collection):
            return []
        chunks: list[Chunk] = []
        offset = None
        while True:
            points, offset = self._client.scroll(
                collection_name=self._collection,
                limit=256,
                offset=offset,
                with_payload=True,
                with_vectors=False,
            )
            for point in points:
                payload = point.payload or {}
                chunks.append(
                    Chunk(
                        chunk_id=payload.get("chunk_id", str(point.id)),
                        text=payload.get("text", ""),
                        source_file=payload.get("source_file", ""),
                        company=payload.get("company", ""),
                        page_number=payload.get("page_number", 0),
                    )
                )
            if offset is None:
                break
        return chunks

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

    def delete_except(self, source_files: list[str]) -> int:
        """Delete points whose source_file is not in the keep-list.

        Selects points where source_file does NOT match any keep entry
        (`must_not` + MatchAny) and deletes them. Counts first so we can report
        how many were removed. Guards against an empty keep-list, which would
        otherwise match nothing in must_not and wipe the whole collection.
        """
        if not source_files:
            raise ValueError("delete_except needs a non-empty keep-list (refusing to wipe all).")
        if not self._client.collection_exists(self._collection):
            return 0
        purge_filter = Filter(
            must_not=[
                FieldCondition(key="source_file", match=MatchAny(any=source_files))
            ]
        )
        to_delete = self._client.count(
            collection_name=self._collection, count_filter=purge_filter, exact=True
        ).count
        if to_delete:
            self._client.delete(
                collection_name=self._collection, points_selector=purge_filter
            )
        return to_delete

    def health_check(self) -> bool:
        try:
            self._client.get_collections()
            return True
        except Exception:
            return False
