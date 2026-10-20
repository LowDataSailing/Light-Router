"""GRIB2 loading and writing through cfgrib/eccodes (group `grib`).

Returns the canonical CF-compliant xarray Dataset (Compatibility rule 1):
a new data source is a new loader, nothing downstream changes. The writer
is the inverse of the loader: the same u10/v10 wind on the same grid,
encoded GRIB2 (the industry exchange format) via the ecCodes bindings
cfgrib already depends on.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import xarray as xr

from light_router.dataset import to_cf_dataset
from light_router.models.weather import WeatherGrid

GRIB_SHORT_NAMES = {"u10": "10u", "v10": "10v"}
"""Our variable names -> GRIB2 shortName (ecCodes parameter table)."""


def _require_eccodes() -> Any:
    """Import the ecCodes bindings lazily, with an actionable error."""
    try:
        import eccodes
    except ImportError as exc:  # pragma: no cover - environment dependent
        raise ImportError(
            "GRIB2 writing requires the optional 'grib' dependency group "
            "(ecCodes bindings): run `uv sync --group grib`"
        ) from exc
    return eccodes


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
        # GRIB2 longitudes are 0..360 (ecCodes stores -26 as 334); the
        # canonical CF convention the repo speaks is [-180, 180).
        ds = ds.assign_coords(
            longitude=((ds["longitude"] + 180.0) % 360.0) - 180.0
        ).sortby("longitude")
        if extent is not None:
            ds = _subset_extent(ds, extent)
        if "time" not in ds["u10"].dims:
            # single-step files carry time as a scalar coordinate
            ds = ds.expand_dims("time")
        u = np.asarray(ds["u10"].values, dtype=np.float32)
        v = np.asarray(ds["v10"].values, dtype=np.float32)
        if u.ndim == 4:
            # one file, one reference time, several lead steps: cfgrib
            # keeps the singleton reference-time axis (time, step, ...)
            u, v = u[0], v[0]
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


def write_grib_wind(grid: WeatherGrid, path: Path, epoch: datetime) -> None:
    """Write the grid's u10/v10 wind as GRIB2 (industry exchange format).

    One message per (variable, time step): a regular lat/lon grid with
    latitude ascending (``jScansPositively``), 10 m above ground, the
    reference time set to ``epoch`` (the calendar instant of weather hour
    0) and the forecast step in whole hours — the layout GFS files use and
    :func:`load_grib_wind` reads back. Time steps must be whole hours;
    finer data belongs to a format that carries it.
    """
    eccodes = _require_eccodes()
    fractional = grid.times[np.abs(grid.times - np.round(grid.times)) > 1e-9]
    if fractional.size:
        raise ValueError(
            f"GRIB2 wind writing needs whole-hour steps, got {fractional[:3]}"
        )
    dlat = float(grid.lats[1] - grid.lats[0]) if len(grid.lats) > 1 else 0.0
    dlon = float(grid.lons[1] - grid.lons[0]) if len(grid.lons) > 1 else 0.0

    with open(path, "wb") as stream:
        for variable, short_name in GRIB_SHORT_NAMES.items():
            for step, hours in enumerate(grid.times):
                handle = eccodes.codes_grib_new_from_samples("regular_ll_sfc_grib2")
                try:
                    eccodes.codes_set(handle, "shortName", short_name)
                    # 10 m above ground (the reader filters on this level)
                    eccodes.codes_set(handle, "typeOfFirstFixedSurface", 103)
                    eccodes.codes_set(handle, "scaleFactorOfFirstFixedSurface", 0)
                    eccodes.codes_set(handle, "scaledValueOfFirstFixedSurface", 10)
                    # geometry: regular ll, both axes ascending
                    eccodes.codes_set(handle, "Ni", len(grid.lons))
                    eccodes.codes_set(handle, "Nj", len(grid.lats))
                    eccodes.codes_set(
                        handle,
                        "latitudeOfFirstGridPointInDegrees",
                        float(grid.lats[0]),
                    )
                    eccodes.codes_set(
                        handle,
                        "longitudeOfFirstGridPointInDegrees",
                        float(grid.lons[0]),
                    )
                    eccodes.codes_set(
                        handle,
                        "latitudeOfLastGridPointInDegrees",
                        float(grid.lats[-1]),
                    )
                    eccodes.codes_set(
                        handle,
                        "longitudeOfLastGridPointInDegrees",
                        float(grid.lons[-1]),
                    )
                    eccodes.codes_set(handle, "iDirectionIncrementInDegrees", dlon)
                    eccodes.codes_set(handle, "jDirectionIncrementInDegrees", dlat)
                    eccodes.codes_set(handle, "iScansNegatively", 0)
                    eccodes.codes_set(handle, "jScansPositively", 1)
                    # reference time = epoch, step = lead hours
                    eccodes.codes_set(handle, "dataDate", int(epoch.strftime("%Y%m%d")))
                    eccodes.codes_set(handle, "dataTime", int(epoch.strftime("%H%M")))
                    eccodes.codes_set(handle, "stepUnits", "h")
                    eccodes.codes_set(handle, "forecastTime", int(round(float(hours))))
                    eccodes.codes_set(handle, "bitsPerValue", 16)
                    eccodes.codes_set_values(
                        handle, np.ascontiguousarray(grid.data[variable][step])
                    )
                    eccodes.codes_write(handle, stream)
                finally:
                    eccodes.codes_release(handle)


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
