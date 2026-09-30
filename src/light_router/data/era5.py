"""ERA5 reanalysis access via the Open-Meteo archive API (no key required).

ERA5 is the measured-weather ground truth for past passages: a reanalysis
that assimilates observations. The operational simulation advances the boat
on ERA5 winds while the router replans on degraded GFS forecasts —
mimicking a real router's forecast-vs-reality gap.

The API is point-based; a grid is fetched by batching many lat/lon pairs
per request and reassembling the regular grid. Wind comes back as
speed (km/h) + meteorological direction (deg, FROM); it is converted to
u10/v10 (m/s) for the canonical CF Dataset.
"""

from __future__ import annotations

import hashlib
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

import numpy as np
import xarray as xr

ERA5_URL = "https://archive-api.open-meteo.com/v1/era5"
KMH_PER_MS = 3.6


def era5_url(
    lats: list[float],
    lons: list[float],
    start_date: str,
    end_date: str,
) -> str:
    """URL of one batched ERA5 request (hourly wind at the given points).

    start_date/end_date: YYYYMMDD or YYYY-MM-DD (UTC).
    """
    params = {
        "latitude": ",".join(f"{v:g}" for v in lats),
        "longitude": ",".join(f"{v:g}" for v in lons),
        "start_date": start_date,
        "end_date": end_date,
        "hourly": "wind_speed_10m,wind_direction_10m",
        "timezone": "UTC",
    }
    return f"{ERA5_URL}?{urllib.parse.urlencode(params)}"


def _fetch_json(url: str, timeout_s: int) -> object:
    with urllib.request.urlopen(url, timeout=timeout_s) as response:
        return json.loads(response.read().decode())


def _fetch_json_throttled(url: str, timeout_s: int, max_retries: int = 60) -> object:
    """Fetch one batch, retrying on the API's rate limit (HTTP 429).

    Open-Meteo weights a multi-location request by its location count, so a
    grid fetch can exceed the per-minute or per-hour call quota; the
    response's Retry-After header says when the quota resets. Long routes
    need more calls than one hourly window allows, so retries are patient
    enough (up to ~60 x 5 min) to bridge an hourly quota reset; a batch
    cache (see fetch_era5_wind_grid) makes any give-up cheap to resume.
    """
    attempt = 0
    while True:
        try:
            return _fetch_json(url, timeout_s)
        except urllib.error.HTTPError as exc:
            if exc.code != 429 or attempt >= max_retries:
                raise
            retry_after = exc.headers.get("Retry-After") if exc.headers else None
            wait_s = float(retry_after) if retry_after else 30.0 * (attempt + 1)
            time.sleep(min(wait_s, 300.0))
            attempt += 1


def _hours_since_start(iso_times: list[str], start_date: str) -> np.ndarray:
    """Hours since start_date 00:00 UTC from ISO timestamps."""
    start = np.datetime64(f"{start_date}T00:00:00")
    times = np.array(iso_times, dtype="datetime64[ns]")
    return (times - start) / np.timedelta64(1, "h")


def fetch_era5_wind_grid(
    lats: np.ndarray,
    lons: np.ndarray,
    start_date: str,
    end_date: str,
    cache_path: Path | None = None,
    batch_size: int = 50,
    timeout_s: int = 120,
    pause_s: float = 6.0,
) -> xr.Dataset:
    """Fetch ERA5 10 m wind on a regular grid as a canonical CF Dataset.

    The time axis is hours since ``start_date`` 00:00 UTC — the absolute
    passage clock. Points are batched ``batch_size`` per request, pausing
    ``pause_s`` between batches to stay under the API's per-minute call
    quota (a batch of N locations counts as N calls). With ``cache_path``,
    every batch response is cached on disk as it arrives, so an interrupted
    fetch (rate-limit give-up, crash) resumes where it left over; the
    assembled grid is then cached at ``cache_path`` so full re-runs are free.
    """
    if cache_path is not None and cache_path.exists():
        return _grid_from_cache(cache_path, lats, lons, start_date)

    lat_values = np.asarray(lats, dtype=float)
    lon_values = np.asarray(lons, dtype=float)
    points = [(float(la), float(lo)) for la in lat_values for lo in lon_values]

    batch_dir = None
    if cache_path is not None:
        fingerprint = hashlib.sha256(
            json.dumps([start_date, end_date, points]).encode()
        ).hexdigest()[:12]
        batch_dir = cache_path.parent / f"{cache_path.name}.batches.{fingerprint}"
        batch_dir.mkdir(parents=True, exist_ok=True)

    locations: list[dict] = []
    for i in range(0, len(points), batch_size):
        batch_path = batch_dir / f"{i:06d}.json" if batch_dir is not None else None
        if batch_path is not None and batch_path.exists():
            locations.extend(json.loads(batch_path.read_text()))
            continue
        if i and pause_s:
            time.sleep(pause_s)
        batch = points[i : i + batch_size]
        url = era5_url(
            [p[0] for p in batch], [p[1] for p in batch], start_date, end_date
        )
        result = _fetch_json_throttled(url, timeout_s)
        if not isinstance(result, list):
            raise ValueError(f"ERA5 API error for batch {i}: {result}")
        if batch_path is not None:
            batch_path.write_text(json.dumps(result))
        locations.extend(result)

    times = _hours_since_start(locations[0]["hourly"]["time"], start_date)
    n_time = len(times)
    speed = np.empty((len(points), n_time), dtype=np.float32)
    direction = np.empty((len(points), n_time), dtype=np.float32)
    for j, loc in enumerate(locations):
        if len(loc["hourly"]["time"]) != n_time:
            raise ValueError("ERA5 locations returned mismatched time axes")
        speed[j] = np.asarray(loc["hourly"]["wind_speed_10m"], dtype=np.float32)
        direction[j] = np.asarray(loc["hourly"]["wind_direction_10m"], dtype=np.float32)

    if cache_path is not None:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(json.dumps(locations))

    return _grid_from_arrays(lat_values, lon_values, times, speed, direction)


def _grid_from_cache(
    cache_path: Path, lats: np.ndarray, lons: np.ndarray, start_date: str
) -> xr.Dataset:
    locations = json.loads(cache_path.read_text())
    lat_values = np.asarray(lats, dtype=float)
    lon_values = np.asarray(lons, dtype=float)
    times = _hours_since_start(locations[0]["hourly"]["time"], start_date)
    n_time = len(times)
    speed = np.empty((len(lat_values) * len(lon_values), n_time), dtype=np.float32)
    direction = np.empty_like(speed)
    for j, loc in enumerate(locations):
        speed[j] = np.asarray(loc["hourly"]["wind_speed_10m"], dtype=np.float32)
        direction[j] = np.asarray(loc["hourly"]["wind_direction_10m"], dtype=np.float32)
    return _grid_from_arrays(lat_values, lon_values, times, speed, direction)


def _grid_from_arrays(
    lat_values: np.ndarray,
    lon_values: np.ndarray,
    times: np.ndarray,
    speed_kmh: np.ndarray,
    direction_deg: np.ndarray,
) -> xr.Dataset:
    """Reshape point samples into a grid and convert to u10/v10 (m/s)."""
    n_lat, n_lon, n_time = len(lat_values), len(lon_values), len(times)
    speed = speed_kmh.reshape(n_lat, n_lon, n_time) / KMH_PER_MS
    wdir = np.deg2rad(direction_deg.reshape(n_lat, n_lon, n_time))
    u = -speed * np.sin(wdir)
    v = -speed * np.cos(wdir)
    # (lat, lon, time) -> (time, lat, lon)
    u10 = np.transpose(u, (2, 0, 1)).astype(np.float32)
    v10 = np.transpose(v, (2, 0, 1)).astype(np.float32)
    return xr.Dataset(
        data_vars={
            "u10": (("time", "latitude", "longitude"), u10),
            "v10": (("time", "latitude", "longitude"), v10),
        },
        coords={
            "time": ("time", times),
            "latitude": ("latitude", lat_values),
            "longitude": ("longitude", lon_values),
        },
    )
