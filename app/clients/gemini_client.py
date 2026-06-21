"""Gemini clients — the only file that imports the google-genai SDK.

GeminiKeyPool rotates API keys on 429 (each free-tier key has its own quota),
shared across GeminiEmbedder and GeminiLLM. Raises 503 once all keys exhaust.
"""

from __future__ import annotations

from typing import Callable, Iterator, TypeVar

from google import genai
from google.genai import errors as genai_errors
from google.genai import types

from app.core.errors import ConfigurationError, UpstreamServiceError
from app.core.interfaces import Embedder, LLMProvider

# Gemini caps how many inputs one embed call accepts; batch under it.
_MAX_BATCH = 100

T = TypeVar("T")


class GeminiKeyPool:
    """Rotating pool of Gemini API keys, shared by the embedder + LLM.

    `run()` retries the next key on a 429 and raises once all keys are spent.
    The index only moves forward, so a daily-capped key isn't retried later.
    """

    def __init__(self, keys: list[str]) -> None:
        if not keys:
            raise ConfigurationError(
                "No Gemini API key set - add GEMINI_API_KEY (and optionally "
                "GEMINI_API_KEY_2 / _3) to .env."
            )
        self._keys = keys
        self._clients: dict[int, genai.Client] = {}
        self._idx = 0

    @property
    def key_count(self) -> int:
        return len(self._keys)

    def _client(self, i: int) -> genai.Client:
        if i not in self._clients:
            self._clients[i] = genai.Client(api_key=self._keys[i])
        return self._clients[i]

    def run(self, action: str, call: Callable[[genai.Client], T]) -> T:
        """Run `call(client)` with key rotation on quota (429); translate other
        failures to UpstreamServiceError (-> HTTP 503)."""
        last_exc: Exception | None = None
        for i in range(self._idx, len(self._keys)):
            self._idx = i
            try:
                return call(self._client(i))
            except genai_errors.APIError as exc:
                if exc.code == 429:  # quota exhausted -> try next key
                    last_exc = exc
                    continue
                raise UpstreamServiceError(
                    f"Gemini failed while {action} (code {exc.code}): {exc.message}. "
                    "This is usually transient — please retry shortly."
                ) from exc
        raise UpstreamServiceError(
            f"All {len(self._keys)} Gemini key(s) are quota-exhausted while {action}. "
            "Add another GEMINI_API_KEY_n or wait for the daily reset."
        ) from last_exc


class GeminiEmbedder(Embedder):
    def __init__(self, pool: GeminiKeyPool, model: str, dimension: int) -> None:
        self._pool = pool
        self._model = model
        self._dimension = dimension

    @property
    def dimension(self) -> int:
        return self._dimension

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        for start in range(0, len(texts), _MAX_BATCH):
            batch = texts[start : start + _MAX_BATCH]
            response = self._pool.run(
                "embedding documents",
                lambda c, b=batch: c.models.embed_content(
                    model=self._model,
                    contents=b,
                    config=types.EmbedContentConfig(
                        task_type="RETRIEVAL_DOCUMENT",
                        output_dimensionality=self._dimension,
                    ),
                ),
            )
            vectors.extend(e.values for e in response.embeddings)
        return vectors

    def embed_query(self, text: str) -> list[float]:
        response = self._pool.run(
            "embedding the query",
            lambda c: c.models.embed_content(
                model=self._model,
                contents=text,
                config=types.EmbedContentConfig(
                    task_type="RETRIEVAL_QUERY",
                    output_dimensionality=self._dimension,
                ),
            ),
        )
        return response.embeddings[0].values


class GeminiLLM(LLMProvider):
    """Generates answers with a Gemini chat model.

    Low temperature keeps answers grounded in the retrieved context.
    """

    def __init__(self, pool: GeminiKeyPool, model: str) -> None:
        self._pool = pool
        self._model = model

    def generate(self, prompt: str) -> str:
        response = self._pool.run(
            "generating the answer",
            lambda c: c.models.generate_content(
                model=self._model,
                contents=prompt,
                config=types.GenerateContentConfig(temperature=0.2),
            ),
        )
        return response.text or ""

    def generate_stream(self, prompt: str) -> Iterator[str]:
        stream = self._pool.run(
            "streaming the answer",
            lambda c: c.models.generate_content_stream(
                model=self._model,
                contents=prompt,
                config=types.GenerateContentConfig(temperature=0.2),
            ),
        )
        for chunk in stream:
            if chunk.text:
                yield chunk.text
