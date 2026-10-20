"""GRIB2 wind writing: the round trip through the industry exchange format."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from experiments.oracle.opencpn import write_wind_field
from experiments.synthetic import SYNTHETIC_EPOCH, trade_wind_field
from light_router.dataset import grid_from_dataset, to_cf_dataset
from light_router.models.weather import WeatherGrid
from light_router.weather_data.grib import load_grib_wind, _write_grib_wind


def _importable(module: str) -> bool:
    try:
        __import__(module)
        return True
    except ImportError:
        return False


pytestmark = pytest.mark.skipif(
    not _importable("eccodes"), reason="needs the optional grib group (ecCodes)"
)


def make_grid() -> WeatherGrid:
    lats = np.arange(12.0, 32.01, 1.0)
    lons = np.arange(-26.0, -12.99, 1.0)
    times = np.arange(0.0, 13.0, 6.0)
    return trade_wind_field(lats, lons, times)


def test__write_grib_wind_round_trips(tmp_path: Path):
    grid = make_grid()
    path = tmp_path / "wind.grib2"
    _write_grib_wind(grid, path, SYNTHETIC_EPOCH)
    back = grid_from_dataset(load_grib_wind(path))
    assert np.allclose(back.lats, grid.lats)
    assert np.allclose(back.lons, grid.lons)  # [-180, 180) convention kept
    assert np.allclose(back.times, grid.times)  # steps = lead hours
    # 16-bit packing: round trip within packing tolerance
    assert np.allclose(back.data["u10"], grid.data["u10"], atol=5e-3)
    assert np.allclose(back.data["v10"], grid.data["v10"], atol=5e-3)


def test_to_grib2_method_round_trips(tmp_path: Path):
    grid = make_grid()
    path = tmp_path / "wind.grib2"
    grid.to_grib2(path, SYNTHETIC_EPOCH)
    back = grid_from_dataset(load_grib_wind(path))
    assert np.allclose(back.data["u10"], grid.data["u10"], atol=5e-3)


def test__write_grib_wind_rejects_fractional_hours(tmp_path: Path):
    lats = np.arange(12.0, 32.01, 1.0)
    lons = np.arange(-26.0, -12.99, 1.0)
    fractional = trade_wind_field(lats, lons, np.array([0.0, 0.5]))
    with pytest.raises(ValueError, match="whole-hour"):
        _write_grib_wind(fractional, tmp_path / "wind.grib2", SYNTHETIC_EPOCH)


def test_write_wind_field_writes_grib2_when_eccodes_available(tmp_path: Path):
    # the OpenCPN adapter's weather input: GRIB2 (magic bytes) when the
    # encoder is importable in this environment
    path = tmp_path / "wind_field.grib2"
    write_wind_field(to_cf_dataset(make_grid()), path, SYNTHETIC_EPOCH)
    assert path.read_bytes()[:4] == b"GRIB"


def test_reference_epoch_sets_the_messages_reference_time(tmp_path: Path):
    from datetime import datetime, timezone

    import xarray as xr

    epoch = datetime(2025, 10, 22, 12, tzinfo=timezone.utc)
    path = tmp_path / "wind.grib2"
    _write_grib_wind(make_grid(), path, epoch)
    raw = xr.open_dataset(
        path,
        engine="cfgrib",
        backend_kwargs={
            "filter_by_keys": {"typeOfLevel": "heightAboveGround", "level": 10}
        },
    )
    # cfgrib's ``time`` coordinate is the GRIB reference time = the epoch
    assert str(raw.time.values)[:16] == "2025-10-22T12:00"
    raw.close()
    # lead hours stay hours since the reference: hour 0 == the epoch
    assert grid_from_dataset(load_grib_wind(path)).times[0] == 0.0
