"""GRIB2 loading through cfgrib/xarray (optional dependency group `grib`)."""

from __future__ import annotations

from pathlib import Path

import numpy as np

from .weather import WeatherGrid


def load_grib_wind(paths: list[Path] | Path) -> WeatherGrid:
    """Load U10/V10 from one or more GFS GRIB2 files into a WeatherGrid.

    Multiple files (one per forecast hour) are merged on the time axis.
    Requires the optional `grib` dependency group (cfgrib + xarray).
    """
    try:
        import xarray  # noqa: F401
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
        ds = __import__("xarray").open_dataset(
            path,
            engine="cfgrib",
            backend_kwargs={
                "filter_by_keys": {"typeOfLevel": "heightAboveGround", "level": 10}
            },
        )
        u = np.asarray(ds["u10"].values, dtype=np.float32)
        v = np.asarray(ds["v10"].values, dtype=np.float32)
        times = _hours_since_first(ds["time"].values)
        grids.append(
            WeatherGrid(
                times=times,
                lats=np.asarray(ds["latitude"].values, dtype=float),
                lons=np.asarray(ds["longitude"].values, dtype=float),
                data={"u10": u, "v10": v},
            )
        )
        ds.close()

    return _merge(grids)


def _hours_since_first(time_values: np.ndarray) -> np.ndarray:
    """Convert numpy datetime64 values to hours since the first step."""
    t = np.asarray(time_values).astype("datetime64[ns]").astype(np.int64) / 3.6e12
    return t - t[0]


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
    times = np.concatenate([g.times for g in grids])
    order = np.argsort(times)
    times = times[order]
    if np.any(np.diff(times) <= 0):
        # keep first occurrence of duplicated steps
        _, first = np.unique(times, return_index=True)
        keep = np.sort(first)
        times = times[keep]
    else:
        keep = order
    data = {
        name: np.concatenate([g.data[name] for g in grids])[keep]
        for name in base.variables
    }
    return WeatherGrid(times=times, lats=base.lats, lons=base.lons, data=data)
