"""Agent router — an LLM classifies a question into one of three routes:

  - answer_from_docs : answerable from the uploaded annual reports (the default)
  - clarify          : too vague/ambiguous — ask the user a one-line follow-up
  - web_search       : needs current/external info not in the filings

Any parse/LLM error falls back to `answer_from_docs`, so the router can never
block the core path.
"""

from __future__ import annotations

import json
import re

from app.core.domain import (
    ROUTE_ANSWER,
    ROUTE_CLARIFY,
    ROUTE_WEB,
    RouteDecision,
)
from app.core.interfaces import LLMProvider, QueryRouter

_VALID_ROUTES = {ROUTE_ANSWER, ROUTE_CLARIFY, ROUTE_WEB}

_ROUTER_PROMPT = """You are the router for FinQuery, a Q&A system over company \
annual reports (10-Ks). Decide how to handle the user's question and reply with \
ONLY a JSON object, no prose:

{{"route": "answer_from_docs" | "clarify" | "web_search", "clarification": "<a \
short follow-up question if route is clarify, else empty>"}}

Guidance:
- "answer_from_docs": about a company's financials/strategy/risks that a 10-K \
would cover (revenue, segments, risk factors, etc.). This is the default.
- "clarify": too vague to answer — no company named, or an unclear metric \
(e.g. "how did they do?"). Give a one-line clarification question.
- "web_search": needs current or post-filing info a 10-K can't contain \
(today's stock price, recent news, this week's events).

Question: {question}
"""


def _extract_json(text: str) -> dict:
    """Pull the first JSON object out of the model's reply (tolerates code fences)."""
    fenced = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.MULTILINE)
    match = re.search(r"\{.*\}", fenced, flags=re.DOTALL)
    if not match:
        raise ValueError("no JSON object in router response")
    return json.loads(match.group(0))


class LLMQueryRouter(QueryRouter):
    def __init__(self, llm: LLMProvider) -> None:
        self._llm = llm

    def route(self, question: str) -> RouteDecision:
        try:
            raw = self._llm.generate(_ROUTER_PROMPT.format(question=question))
            data = _extract_json(raw)
            route = str(data.get("route", "")).strip()
            if route not in _VALID_ROUTES:
                route = ROUTE_ANSWER
            clarification = (data.get("clarification") or "").strip() or None
            # Only meaningful for the clarify route; ignore otherwise.
            if route != ROUTE_CLARIFY:
                clarification = None
            return RouteDecision(route=route, clarification=clarification)
        except Exception:  # noqa: BLE001 — never let routing break the query path
            # Safe default: behave like the non-agent pipeline.
            return RouteDecision(route=ROUTE_ANSWER, reason="router fallback")
