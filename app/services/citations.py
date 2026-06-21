"""Citations — maps retrieval hits to their source + page for display."""

from __future__ import annotations

from app.core.domain import SearchHit

_SNIPPET_CHARS = 240


def build_citations(hits: list[SearchHit]) -> list[dict]:
    """Turn retrieval hits into plain citation dicts (router maps to schema)."""
    citations: list[dict] = []
    for hit in hits:
        chunk = hit.chunk
        snippet = chunk.text.strip().replace("\n", " ")
        if len(snippet) > _SNIPPET_CHARS:
            snippet = snippet[:_SNIPPET_CHARS].rstrip() + "…"
        citations.append(
            {
                "source_file": chunk.source_file,
                "company": chunk.company,
                "page_number": chunk.page_number,
                "snippet": snippet,
                "score": round(hit.score, 4),
            }
        )
    return citations
