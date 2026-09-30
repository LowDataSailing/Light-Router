"""Compatibility rule 1: the canonical CF xarray Dataset round-trip."""

from __future__ import annotations

import numpy as np
import pytest

from light_router.dataset import dataset_extent, grid_from_dataset, to_cf_dataset
from light_router.synthetic import trade_wind_field


def make_grid():
    lats = np.arange(12.0, 32.01, 1.0)
    lons = np.arange(-26.0, -12.99, 1.0)
    times = np.arange(0.0, 49.0, 6.0)
    return trade_wind_field(
        lats, lons, times, mean_speed_kt=15.0, direction_from_deg=45.0
    )


def test_roundtrip_preserves_data():
    grid = make_grid()
    ds = to_cf_dataset(grid)
    back = grid_from_dataset(ds)
    assert np.allclose(back.times, grid.times)
    assert np.allclose(back.lats, grid.lats)
    assert np.allclose(back.lons, grid.lons)
    for name in ("u10", "v10"):
        assert np.allclose(back.data[name], grid.data[name])


def test_cf_structure_and_attrs():
    ds = to_cf_dataset(make_grid())
    assert set(ds.dims) == {"time", "latitude", "longitude"}
    assert set(ds.data_vars) >= {"u10", "v10"}
    assert ds["u10"].attrs["standard_name"] == "eastward_wind"
    assert ds["u10"].attrs["units"] == "m s-1"
    assert ds["time"].attrs["units"] == "hours since forecast initialization"
    assert ds["latitude"].attrs["units"] == "degrees_north"
    assert ds["longitude"].attrs["units"] == "degrees_east"


def test_grid_from_dataset_sorts_axes():
    ds = to_cf_dataset(make_grid())
    shuffled = ds.isel(time=list(range(ds.sizes["time"]))[::-1])
    grid = grid_from_dataset(shuffled)
    assert np.all(np.diff(grid.times) > 0)
    # values follow their coordinates: first sorted step is the shuffled last
    assert np.allclose(grid.data["u10"][0], ds["u10"].isel(time=-1).values)


def test_grid_from_dataset_rejects_missing_dims():
    ds = to_cf_dataset(make_grid()).rename({"time": "step"})
    with pytest.raises(ValueError, match="canonical dimensions"):
        grid_from_dataset(ds)


def test_grid_from_dataset_rejects_missing_wind():
    ds = to_cf_dataset(make_grid()).drop_vars("v10")
    with pytest.raises(ValueError, match="v10"):
        grid_from_dataset(ds)


def test_dataset_extent():
    ds = to_cf_dataset(make_grid())
    lon_min, lon_max, lat_min, lat_max = dataset_extent(ds)
    assert lon_min == pytest.approx(-26.0)
    assert lon_max == pytest.approx(-13.0)
    assert lat_min == pytest.approx(12.0)
    assert lat_max == pytest.approx(32.0)


def test_extra_variables_survive():
    grid = make_grid()
    grid.data["msl"] = np.full(grid.data["u10"].shape, 101300.0, dtype=np.float32)
    ds = to_cf_dataset(grid)
    assert "msl" in ds.data_vars
    back = grid_from_dataset(ds)
    assert "msl" in back.data
    assert back.data["msl"].shape == back.data["u10"].shape
