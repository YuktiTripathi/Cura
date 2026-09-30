"""Shared HTTP client. Callers must not open a new client per request."""

from __future__ import annotations

import httpx

_client: httpx.Client | None = None


def get_http_client() -> httpx.Client:
    global _client
    if _client is None or _client.is_closed:
        _client = httpx.Client(
            timeout=httpx.Timeout(30.0, connect=5.0),
            limits=httpx.Limits(max_keepalive_connections=20, max_connections=40),
        )
    return _client


def close_http_client() -> None:
    global _client
    if _client is not None and not _client.is_closed:
        _client.close()
    _client = None
