"""Citations — maps the chunks used in an answer back to their source + page.

Pure transformation logic (no external dependencies), so it's trivially
testable. Takes the retrieval hits and produces the citation list the frontend
renders under each answer as proof the answer is grounded.
"""

from __future__ import annotations

from app.core.domain import SearchHit

_SNIPPET_CHARS = 240


def build_citations(hits: list[SearchHit]) -> list[dict]:
    """Turn retrieval hits into lightweight citation dicts.

    Returns plain dicts (not Pydantic) so this stays framework-agnostic; the
    router maps them into the Citation response schema.
    """
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
