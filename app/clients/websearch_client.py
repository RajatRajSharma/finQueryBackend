"""Web search client — the agent's fallback when a question isn't in the docs.

Default provider is DuckDuckGo via the keyless `ddgs` package, opt-in behind
ENABLE_WEB_SEARCH. Lazy-imported by the factory only when enabled, so `ddgs`
isn't a hard dependency on the normal path.
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

from ddgs import DDGS

from app.core.domain import WebResult
from app.core.errors import UpstreamServiceError
from app.core.interfaces import WebSearchTool


@contextmanager
def _translate_websearch_errors(action: str) -> Iterator[None]:
    """Map web-search failures to a clean UpstreamServiceError -> HTTP 503."""
    try:
        yield
    except Exception as exc:  # noqa: BLE001 — any provider/transport failure is "upstream"
        raise UpstreamServiceError(
            f"Web search failed while {action}: {exc}. Please retry shortly."
        ) from exc


class DuckDuckGoSearch(WebSearchTool):
    def __init__(self, max_results: int) -> None:
        self._max_results = max_results

    def search(self, query: str) -> list[WebResult]:
        with _translate_websearch_errors("querying DuckDuckGo"):
            with DDGS() as ddgs:
                raw = list(ddgs.text(query, max_results=self._max_results))
        return [
            WebResult(
                title=r.get("title", ""),
                url=r.get("href", "") or r.get("url", ""),
                snippet=r.get("body", "") or r.get("snippet", ""),
            )
            for r in raw
        ]
