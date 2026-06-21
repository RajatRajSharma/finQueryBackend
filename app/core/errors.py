"""Domain-specific exception types, mapped to HTTP status by the single
exception handler in main.py."""

from __future__ import annotations


class ConfigurationError(RuntimeError):
    """A required setting is missing or invalid (e.g. an unset API key).
    Surfaced as HTTP 503.
    """


class UpstreamServiceError(RuntimeError):
    """A downstream vendor API (Gemini, etc.) failed transiently.

    Covers overload, rate limits, timeouts, and 5xx from a provider SDK.
    Surfaced as HTTP 503; retrying shortly usually succeeds.
    """
