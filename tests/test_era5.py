"""ERA5 client: URL building and wind conversion (no network)."""

from __future__ import annotations

import numpy as np

from light_router.weather_data.era5 import (
    _grid_from_arrays,
    _hours_since_start,
    era5_url,
)


def test_era5_url_batches_points():
    url = era5_url([28.0, 24.0], [-15.5, -18.5], "2025-09-01", "2025-09-07")
    assert url.startswith("https://archive-api.open-meteo.com/v1/era5?")
    assert "latitude=28%2C24" in url
    assert "longitude=-15.5%2C-18.5" in url
    assert "start_date=2025-09-01" in url
    assert "hourly=wind_speed_10m%2Cwind_direction_10m" in url


def test_hours_since_start():
    hours = _hours_since_start(
        ["2025-09-01T00:00", "2025-09-01T06:00", "2025-09-02T00:00"],
        "2025-09-01",
    )
    assert hours[0] == 0.0
    assert hours[1] == 6.0
    assert hours[2] == 24.0


def test_grid_from_arrays_converts_wind():
    """speed/dir (km/h, FROM) -> u/v (m/s); layout (time, lat, lon)."""
    lats = np.array([10.0, 10.5])
    lons = np.array([-20.0, -19.5])
    times = np.array([0.0, 6.0])
    # one point sample per (lat, lon): 4 points, 2 times
    speed = np.array([[10.0, 20.0], [10.0, 20.0], [10.0, 20.0], [10.0, 20.0]])
    direction = np.zeros((4, 2))  # wind from north
    ds = _grid_from_arrays(lats, lons, times, speed, direction)
    assert dict(ds.sizes) == {"time": 2, "latitude": 2, "longitude": 2}
    # wind from the north blows southward: u ~ 0, v < 0
    u10 = ds["u10"].values
    v10 = ds["v10"].values
    assert np.allclose(u10, 0.0, atol=1e-6)
    assert np.all(v10 < 0)
    # 10 km/h from north at t=0, 20 km/h at t=6
    assert np.allclose(np.abs(v10[0]), 10.0 / 3.6, atol=1e-4)
    assert np.allclose(np.abs(v10[1]), 20.0 / 3.6, atol=1e-4)


def test_fetch_uses_throttled_downloader(monkeypatch):
    """The grid fetch goes through the rate-limited downloader, batch by batch."""
    from light_router.weather_data import era5

    payload = [
        {
            "hourly": {
                "time": ["2025-09-01T00:00", "2025-09-01T01:00"],
                "wind_speed_10m": [10.0, 10.0],
                "wind_direction_10m": [0.0, 0.0],
            }
        }
        for _ in range(2)
    ]
    calls: list[str] = []

    def fake_fetch(url: str, timeout_s: int) -> object:
        calls.append(url)
        return payload

    monkeypatch.setattr(era5, "fetch_json_throttled", fake_fetch)
    ds = era5.fetch_era5_wind_grid(
        np.array([10.0, 10.5]),
        np.array([-20.0, -19.5]),
        "2025-09-01",
        "2025-09-01",
        batch_size=2,
        pause_s=0.0,
    )
    assert len(calls) == 2  # one call per batch
    assert dict(ds.sizes) == {"time": 2, "latitude": 2, "longitude": 2}


def test_fetch_resumes_from_batch_cache(tmp_path, monkeypatch):
    """Already-fetched batches are read from disk, not re-requested."""
    import hashlib
    import json

    from light_router.weather_data import era5

    lats = np.array([10.0, 10.5])
    lons = np.array([-20.0, -19.5])
    points = [(float(la), float(lo)) for la in lats for lo in lons]
    payload = [
        {
            "hourly": {
                "time": ["2025-09-01T00:00", "2025-09-01T01:00"],
                "wind_speed_10m": [10.0, 10.0],
                "wind_direction_10m": [0.0, 0.0],
            }
        }
        for _ in range(2)
    ]

    cache_path = tmp_path / "era5.json"
    fingerprint = hashlib.sha256(
        json.dumps(["2025-09-01", "2025-09-01", points]).encode()
    ).hexdigest()[:12]
    batch_dir = tmp_path / f"era5.json.batches.{fingerprint}"
    batch_dir.mkdir(parents=True)
    (batch_dir / "000000.json").write_text(json.dumps(payload))  # batch 0 done

    calls: list[str] = []

    def fake_fetch(url: str, timeout_s: int) -> object:
        calls.append(url)
        return payload

    monkeypatch.setattr(era5, "fetch_json_throttled", fake_fetch)
    ds = era5.fetch_era5_wind_grid(
        lats,
        lons,
        "2025-09-01",
        "2025-09-01",
        cache_path=cache_path,
        batch_size=2,
        pause_s=0.0,
    )
    assert len(calls) == 1  # only batch 1 was fetched
    assert (batch_dir / "000002.json").exists()
    assert cache_path.exists()  # assembled grid cached for full re-runs
    assert dict(ds.sizes) == {"time": 2, "latitude": 2, "longitude": 2}
