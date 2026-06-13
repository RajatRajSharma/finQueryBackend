"""Gemini clients — the ONLY file that imports the google-genai SDK.

Holds both Gemini-backed implementations:
  - GeminiEmbedder -> Embedder      (embeds text)
  - GeminiLLM      -> LLMProvider   (generates answers)

To add OpenAI, create app/clients/openai_client.py with sibling classes and
register them in app/core/factory.py — nothing else in the codebase changes.

Document vs query embeddings use different task types (RETRIEVAL_DOCUMENT vs
RETRIEVAL_QUERY); Gemini uses that hint to place them in a compatible space.
"""

from __future__ import annotations

from google import genai
from google.genai import types

from app.core.errors import ConfigurationError
from app.core.interfaces import Embedder, LLMProvider

# Gemini caps how many inputs one embed call accepts; batch under it.
_MAX_BATCH = 100


class GeminiEmbedder(Embedder):
    def __init__(self, api_key: str, model: str, dimension: int) -> None:
        if not api_key:
            raise ConfigurationError(
                "GEMINI_API_KEY is empty - set it in .env before ingesting."
            )
        self._client = genai.Client(api_key=api_key)
        self._model = model
        self._dimension = dimension

    @property
    def dimension(self) -> int:
        return self._dimension

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        for start in range(0, len(texts), _MAX_BATCH):
            batch = texts[start : start + _MAX_BATCH]
            response = self._client.models.embed_content(
                model=self._model,
                contents=batch,
                config=types.EmbedContentConfig(
                    task_type="RETRIEVAL_DOCUMENT",
                    output_dimensionality=self._dimension,
                ),
            )
            vectors.extend(e.values for e in response.embeddings)
        return vectors

    def embed_query(self, text: str) -> list[float]:
        response = self._client.models.embed_content(
            model=self._model,
            contents=text,
            config=types.EmbedContentConfig(
                task_type="RETRIEVAL_QUERY",
                output_dimensionality=self._dimension,
            ),
        )
        return response.embeddings[0].values


class GeminiLLM(LLMProvider):
    """Generates answers with a Gemini chat model.

    Low temperature keeps answers grounded and repeatable — we want the model
    to stick to the retrieved context, not get creative.
    """

    def __init__(self, api_key: str, model: str) -> None:
        if not api_key:
            raise ConfigurationError(
                "GEMINI_API_KEY is empty - set it in .env before querying."
            )
        self._client = genai.Client(api_key=api_key)
        self._model = model

    def generate(self, prompt: str) -> str:
        response = self._client.models.generate_content(
            model=self._model,
            contents=prompt,
            config=types.GenerateContentConfig(temperature=0.2),
        )
        return response.text or ""
