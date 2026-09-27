"""GRIB2 loading through cfgrib (optional dependency group `grib`).

Returns the canonical CF-compliant xarray Dataset (Compatibility rule 1):
a new data source is a new loader, nothing downstream changes.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import xarray as xr

from .dataset import to_cf_dataset
from .weather import WeatherGrid


def load_grib_wind(
    paths: list[Path] | Path,
    extent: tuple[float, float, float, float] | None = None,
) -> xr.Dataset:
    """Load U10/V10 from one or more GFS GRIB2 files into a CF Dataset.

    Multiple files (one per forecast hour) are merged on the time axis.
    ``extent`` = (lon_min, lon_max, lat_min, lat_max) crops each file to a
    subregion before merging (archive files are global; the crop must not
    cross the antimeridian). Requires the optional `grib` dependency group
    (cfgrib).
    """
    try:
        import cfgrib  # noqa: F401
    except ImportError as exc:  # pragma: no cover - environment dependent
        raise ImportError(
            "GRIB loading requires the optional 'grib' dependency group: "
            "run `uv sync --group grib`"
        ) from exc

    if isinstance(paths, Path):
        paths = [paths]

    grids: list[WeatherGrid] = []
    for path in paths:
        ds = xr.open_dataset(
            path,
            engine="cfgrib",
            backend_kwargs={
                "filter_by_keys": {"typeOfLevel": "heightAboveGround", "level": 10}
            },
        )
        if extent is not None:
            ds = _subset_extent(ds, extent)
        if "time" not in ds["u10"].dims:
            # single-step files carry time as a scalar coordinate
            ds = ds.expand_dims("time")
        u = np.asarray(ds["u10"].values, dtype=np.float32)
        v = np.asarray(ds["v10"].values, dtype=np.float32)
        times = _forecast_hours(ds)
        grids.append(
            WeatherGrid(
                times=times,
                lats=np.asarray(ds["latitude"].values, dtype=float),
                lons=np.asarray(ds["longitude"].values, dtype=float),
                data={"u10": u, "v10": v},
            )
        )
        ds.close()

    return to_cf_dataset(_merge(grids))


def _subset_extent(
    ds: xr.Dataset, extent: tuple[float, float, float, float]
) -> xr.Dataset:
    """Crop to (lon_min, lon_max, lat_min, lat_max), normalizing longitude.

    GFS archive files are global with longitude 0..359.75 and descending
    latitude; convert longitude to [-180, 180), sort both axes ascending,
    then slice. The extent must not cross the antimeridian.
    """
    lon_min, lon_max, lat_min, lat_max = extent
    ds = ds.assign_coords(longitude=((ds["longitude"] + 180.0) % 360.0) - 180.0)
    ds = ds.sortby("latitude").sortby("longitude")
    return ds.sel(
        latitude=slice(lat_min, lat_max),
        longitude=slice(lon_min, lon_max),
    )


def _forecast_hours(ds: xr.Dataset) -> np.ndarray:
    """Forecast lead time of each step, in hours since initialization.

    Per-hour files each carry one step; the lead time (cfgrib's ``step``,
    valid_time minus initialization) — not hours since the file's own first
    step — is what places them on the merged time axis.
    """
    step = np.atleast_1d(np.asarray(ds["step"].values).astype("timedelta64[ns]"))
    return step.astype(np.int64) / 3.6e12


def _merge(grids: list[WeatherGrid]) -> WeatherGrid:
    """Merge per-hour grids sharing the same spatial axes."""
    if len(grids) == 1:
        return grids[0]
    base = grids[0]
    for other in grids[1:]:
        if not (
            np.array_equal(base.lats, other.lats)
            and np.array_equal(base.lons, other.lons)
        ):
            raise ValueError(
                "GRIB files have mismatched spatial grids; "
                "download them with the same subregion"
            )
    times_all = np.concatenate([g.times for g in grids])
    data_all = {
        name: np.concatenate([g.data[name] for g in grids]) for name in base.variables
    }
    # sort times AND data together, then keep the first of each duplicated step
    order = np.argsort(times_all, kind="stable")
    times = times_all[order]
    unique_mask = np.ones(times.shape, dtype=bool)
    unique_mask[1:] = times[1:] != times[:-1]
    times = times[unique_mask]
    data = {name: data_all[name][order][unique_mask] for name in base.variables}
    return WeatherGrid(times=times, lats=base.lats, lons=base.lons, data=data)
