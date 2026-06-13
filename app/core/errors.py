"""Domain-specific exception types + the HTTP status they map to.

Keeping our own exception hierarchy (instead of raising bare ValueError) lets
the API layer translate engine problems into clean, intentional HTTP responses
via a single exception handler in main.py — rather than leaking 500s. Add new
error types here as the engine grows (e.g. UnsupportedDocumentError).
"""

from __future__ import annotations


class ConfigurationError(RuntimeError):
    """A required setting is missing or invalid (e.g. an unset API key).

    Surfaced to clients as HTTP 503 Service Unavailable — the service is
    correctly built but not yet configured to do the work.
    """
