"""Shared HTTP downloading for the weather-data clients.

One place for the failure modes every client hits on a long fetch:
transient server errors (S3 5xx, connection resets, timeouts) and API rate
limits (HTTP 429 with Retry-After). Clients import the fetchers they need
and own their API-specific parsing; tests patch the fetchers at the client
module.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from typing import TypeVar

_T = TypeVar("_T")


def _fetch_bytes(url: str, timeout_s: int) -> bytes:
    with urllib.request.urlopen(url, timeout=timeout_s) as response:
        return response.read()


def fetch_bytes(url: str, timeout_s: int = 120) -> bytes:
    """GET a URL, returning the raw payload."""
    return _fetch_bytes(url, timeout_s)


def fetch_text(url: str, timeout_s: int = 120) -> str:
    """GET a URL, decoding the payload as text."""
    return _fetch_bytes(url, timeout_s).decode()


def fetch_json(url: str, timeout_s: int = 120) -> object:
    """GET a URL, decoding the payload as JSON."""
    return json.loads(_fetch_bytes(url, timeout_s).decode())


def fetch_range(url: str, start: int, end: int, timeout_s: int = 120) -> bytes:
    """GET ``[start, end)`` of a URL with an HTTP Range request."""
    request = urllib.request.Request(url, headers={"Range": f"bytes={start}-{end - 1}"})
    with urllib.request.urlopen(request, timeout=timeout_s) as response:
        return response.read()


def retry_transient(
    fetch: Callable[..., _T], *args: object, max_retries: int = 5
) -> _T:
    """Run one HTTP fetch, retrying transient server/network errors.

    The S3 archive occasionally answers a range request with a 5xx or
    resets the connection; a multi-thousand-file archive fetch must ride
    those out instead of failing the whole run. Non-5xx HTTP errors (e.g.
    a genuinely missing file) raise immediately.
    """
    for attempt in range(max_retries + 1):
        try:
            return fetch(*args)
        except urllib.error.HTTPError as exc:
            if exc.code < 500 or attempt >= max_retries:
                raise
        except (urllib.error.URLError, TimeoutError, ConnectionError):
            if attempt >= max_retries:
                raise
        time.sleep(min(30.0 * (attempt + 1), 120.0))
    raise AssertionError("unreachable")


def fetch_json_throttled(
    url: str, timeout_s: int = 120, max_retries: int = 60
) -> object:
    """Fetch one JSON payload, retrying on the API's rate limit (HTTP 429).

    Open-Meteo weights a multi-location request by its location count, so a
    grid fetch can exceed the per-minute or per-hour call quota; the
    response's Retry-After header says when the quota resets. Long routes
    need more calls than one hourly window allows, so retries are patient
    enough (up to ~60 x 5 min) to bridge an hourly quota reset; a batch
    cache at the client makes any give-up cheap to resume.
    """
    attempt = 0
    while True:
        try:
            return fetch_json(url, timeout_s)
        except urllib.error.HTTPError as exc:
            if exc.code != 429 or attempt >= max_retries:
                raise
            retry_after = exc.headers.get("Retry-After") if exc.headers else None
            wait_s = float(retry_after) if retry_after else 30.0 * (attempt + 1)
            time.sleep(min(wait_s, 300.0))
            attempt += 1
