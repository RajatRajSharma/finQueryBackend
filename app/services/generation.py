"""GenerationService — turns a question + retrieved chunks into an answer.

Builds the prompt here; the model call lives behind the LLMProvider interface.
The prompt restricts the model to the provided context to keep faithfulness high.
"""

from __future__ import annotations

from typing import Iterator

from app.core.domain import Chunk, WebResult
from app.core.interfaces import LLMProvider

_SYSTEM_INSTRUCTION = (
    "You are FinQuery, a financial analyst assistant. Answer the user's "
    "question using ONLY the context excerpts from company annual reports "
    "below. If the answer is not contained in the context, say you don't have "
    "that information in the provided documents. Be concise and precise with "
    "figures. Cite the company and page when relevant."
)


def build_prompt(question: str, contexts: list[Chunk]) -> str:
    """Assemble the grounding prompt from the question and retrieved chunks."""
    if contexts:
        blocks = [
            f"[{i}] ({c.company}, {c.source_file} p.{c.page_number})\n{c.text}"
            for i, c in enumerate(contexts, start=1)
        ]
        context_text = "\n\n".join(blocks)
    else:
        context_text = "(no relevant context was retrieved)"

    return (
        f"{_SYSTEM_INSTRUCTION}\n\n"
        f"--- CONTEXT ---\n{context_text}\n\n"
        f"--- QUESTION ---\n{question}\n\n"
        f"--- ANSWER ---\n"
    )


_WEB_INSTRUCTION = (
    "You are FinQuery. The user's question was NOT covered by the uploaded "
    "annual reports, so answer using ONLY the web search results below. Begin "
    "your answer with 'From the web:' to make clear this is not from the user's "
    "documents. Be concise and cite the source titles you used."
)


def build_web_prompt(question: str, results: list[WebResult]) -> str:
    """Assemble a prompt grounded in web-search results (the agent fallback)."""
    if results:
        blocks = [f"[{i}] {r.title} ({r.url})\n{r.snippet}" for i, r in enumerate(results, 1)]
        context_text = "\n\n".join(blocks)
    else:
        context_text = "(no web results were found)"
    return (
        f"{_WEB_INSTRUCTION}\n\n"
        f"--- WEB RESULTS ---\n{context_text}\n\n"
        f"--- QUESTION ---\n{question}\n\n"
        f"--- ANSWER ---\n"
    )


class GenerationService:
    def __init__(self, llm: LLMProvider) -> None:
        self._llm = llm

    def generate_answer(self, question: str, contexts: list[Chunk]) -> str:
        prompt = build_prompt(question, contexts)
        return self._llm.generate(prompt)

    def generate_answer_stream(
        self, question: str, contexts: list[Chunk]
    ) -> Iterator[str]:
        """Stream the answer as text deltas (same prompt as generate_answer)."""
        prompt = build_prompt(question, contexts)
        yield from self._llm.generate_stream(prompt)

    def generate_web_answer(self, question: str, results: list[WebResult]) -> str:
        """Answer from web-search results (the agent's web_search fallback)."""
        return self._llm.generate(build_web_prompt(question, results))

    def generate_web_answer_stream(
        self, question: str, results: list[WebResult]
    ) -> Iterator[str]:
        yield from self._llm.generate_stream(build_web_prompt(question, results))
