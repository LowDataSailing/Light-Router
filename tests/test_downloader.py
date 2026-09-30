"""The shared downloader: retry and rate-limit behavior (no network)."""

from __future__ import annotations

import urllib.error

import pytest

from light_router.weather_data import downloader


def test_retry_transient_rides_out_5xx(monkeypatch):
    """A transient S3 500 is retried, not fatal; a 404 raises immediately."""
    calls: list[str] = []
    sleeps: list[float] = []
    monkeypatch.setattr(downloader.time, "sleep", lambda s: sleeps.append(s))

    def flaky(url, timeout_s):
        calls.append(url)
        if len(calls) <= 2:
            raise urllib.error.HTTPError(url, 500, "Internal Server Error", {}, None)
        return "ok"

    assert downloader.retry_transient(flaky, "u", 60) == "ok"
    assert len(calls) == 3
    assert sleeps == [30.0, 60.0]

    def missing(url, timeout_s):
        raise urllib.error.HTTPError(url, 404, "Not Found", {}, None)

    with pytest.raises(urllib.error.HTTPError):
        downloader.retry_transient(missing, "u", 60)
    assert len(calls) == 3  # the 404 was not retried


def test_fetch_json_throttled_retries_on_rate_limit(monkeypatch):
    """A 429 from the API is retried after Retry-After, not fatal."""
    calls: list[str] = []

    def fake_fetch(url: str, timeout_s: int) -> object:
        calls.append(url)
        if len(calls) == 1:
            raise urllib.error.HTTPError(
                url, 429, "Too Many Requests", {"Retry-After": "0"}, None
            )
        return {"ok": True}

    sleeps: list[float] = []
    monkeypatch.setattr(downloader, "fetch_json", fake_fetch)
    monkeypatch.setattr(downloader.time, "sleep", lambda s: sleeps.append(s))
    assert downloader.fetch_json_throttled("https://example.test", 60) == {"ok": True}
    assert len(calls) == 2  # 429, then the retry
    assert sleeps == [0.0]  # honored Retry-After


def test_fetch_json_throttled_gives_up_after_max_retries(monkeypatch):
    """A persistent 429 raises once the retry budget is spent."""

    def always_429(url: str, timeout_s: int) -> object:
        raise urllib.error.HTTPError(
            url, 429, "Too Many Requests", {"Retry-After": "0"}, None
        )

    monkeypatch.setattr(downloader, "fetch_json", always_429)
    monkeypatch.setattr(downloader.time, "sleep", lambda s: None)
    with pytest.raises(urllib.error.HTTPError):
        downloader.fetch_json_throttled("https://example.test", 60, max_retries=3)
