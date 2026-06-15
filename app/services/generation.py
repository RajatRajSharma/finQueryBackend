"""GenerationService — turns a question + retrieved chunks into an answer.

This is the "augment -> generate" half of the RAG mental model. It depends only
on the LLMProvider interface, so it neither knows nor cares whether Gemini or
OpenAI is behind it. The prompt is built here (one responsibility: assembling
context + instructions); the actual model call lives in the provider.

Grounding rule: the prompt explicitly tells the model to answer ONLY from the
provided context and to say so when the answer isn't there — that's what keeps
faithfulness high and hallucinations low (measured later by RAGAS).
"""

from __future__ import annotations

from typing import Iterator

from app.core.domain import Chunk
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
