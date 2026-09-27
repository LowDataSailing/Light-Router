"""The canonical weather representation: a CF-compliant xarray Dataset.

Compatibility rule 1 (specs/compatibility-principles.md): the in-memory
weather representation is a CF-compliant xarray Dataset (dimensions time,
latitude, longitude; variables u10, v10, ...; time = hours since forecast
initialization). Loaders produce it, routers and the harness consume it.
``WeatherGrid`` is the transitional internal numpy view used by the
in-process isochrone engine; it must not appear in any public interface.
"""

from __future__ import annotations

import numpy as np
import xarray as xr

from .weather import WeatherGrid

CF_VARIABLES: dict[str, dict[str, str]] = {
    "u10": {"standard_name": "eastward_wind", "units": "m s-1"},
    "v10": {"standard_name": "northward_wind", "units": "m s-1"},
    "msl": {"standard_name": "air_pressure_at_mean_sea_level", "units": "Pa"},
}


def to_cf_dataset(grid: WeatherGrid) -> xr.Dataset:
    """Convert the internal grid view into the canonical CF Dataset."""
    coords = {
        "time": (
            "time",
            np.asarray(grid.times, dtype=float),
            {"units": "hours since forecast initialization", "axis": "T"},
        ),
        "latitude": (
            "latitude",
            np.asarray(grid.lats, dtype=float),
            {"units": "degrees_north", "standard_name": "latitude", "axis": "Y"},
        ),
        "longitude": (
            "longitude",
            np.asarray(grid.lons, dtype=float),
            {"units": "degrees_east", "standard_name": "longitude", "axis": "X"},
        ),
    }
    data_vars = {}
    for name in grid.variables:
        attrs = dict(CF_VARIABLES.get(name, {}))
        attrs["long_name"] = name
        data_vars[name] = (("time", "latitude", "longitude"), grid.data[name], attrs)
    return xr.Dataset(data_vars=data_vars, coords=coords)


def grid_from_dataset(dataset: xr.Dataset) -> WeatherGrid:
    """Build the internal grid view from a canonical CF Dataset.

    Validates the contract: dims (time, latitude, longitude), strictly
    increasing axes, and at least the u10/v10 wind variables.
    """
    missing = [d for d in ("time", "latitude", "longitude") if d not in dataset.dims]
    if missing:
        raise ValueError(f"dataset is missing canonical dimensions: {missing}")
    for var in ("u10", "v10"):
        if var not in dataset:
            raise ValueError(f"dataset is missing required variable {var!r}")

    dataset = dataset.sortby("time").sortby("latitude").sortby("longitude")
    times = np.asarray(dataset["time"].values, dtype=float)
    lats = np.asarray(dataset["latitude"].values, dtype=float)
    lons = np.asarray(dataset["longitude"].values, dtype=float)
    data = {
        str(name): np.asarray(dataset[name].values)
        for name in dataset.data_vars
        if set(dataset[name].dims) == {"time", "latitude", "longitude"}
    }
    return WeatherGrid(times=times, lats=lats, lons=lons, data=data)


def dataset_extent(dataset: xr.Dataset) -> tuple[float, float, float, float]:
    """Bounding box (lon_min, lon_max, lat_min, lat_max) of the dataset."""
    return (
        float(dataset["longitude"].min()),
        float(dataset["longitude"].max()),
        float(dataset["latitude"].min()),
        float(dataset["latitude"].max()),
    )
