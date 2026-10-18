"""libweatherrouting oracle adapter: the live in-process cross-check.

Wraps ``LinearBestIsoRouter`` from libweatherrouting (PyPI package
``weatherrouting``, pure Python, GPLv3) as a second Router adapter over the
same seam as the isochrone surrogate. The package stays an optional
dependency (group ``oracle``): it is imported lazily inside this module's
functions only, never from ``src/``, so the core router stack carries no
GPLv3 obligation.

The adapter feeds libweatherrouting our weather grid through its ``Grib``
interface (a duck-typed wrapper — the library never isinstance-checks it)
and our polar through its tab-separated polar format, then steps
``Routing`` until the waypoint is reached or the horizon is exhausted.
"""

from __future__ import annotations

import tempfile
from dataclasses import dataclass, field, replace
from datetime import datetime, timedelta
from importlib import metadata
from pathlib import Path
from typing import Any

import numpy as np
import xarray as xr

from light_router.dataset import grid_from_dataset
from light_router.models.route import Route, Waypoint
from light_router.models.vessel import PolarTable
from light_router.models.weather import WeatherGrid
from experiments.synthetic import SYNTHETIC_EPOCH

LIBWEATHERROUTING_PACKAGE = "weatherrouting"
"""PyPI package name of libweatherrouting (the import name is the same)."""

KT_PER_MS = 1.94384
"""Knots per m/s — the unit seam between our grid (m/s) and the library."""


@dataclass
class LibWeatherRoutingConfig:
    """Tuning surface for the libweatherrouting run."""

    dt_hours: float = 1.0
    """Isochrone time step (h) — one ``Routing.step`` per level."""

    min_increase_nm: float = 10.0
    """LinearBestIsoRouter arrival radius around the waypoint (nm)."""

    subdiv: int = 1
    """Isochrone filtering subdivision (deg): one retained isochrone point
    per bearing-from-start bin. 1 is the library default (finest); higher
    values trade resolution for runtime in batch validation."""

    max_hours: float = 240.0
    """Planning horizon (h); a route that cannot finish within it is
    returned as partial (``reached`` is False)."""

    def __post_init__(self) -> None:
        if self.dt_hours <= 0:
            raise ValueError("dt_hours must be positive")
        if self.min_increase_nm <= 0:
            raise ValueError("min_increase_nm must be positive")
        if self.subdiv < 1:
            raise ValueError("subdiv must be at least 1")


class _GridGrib:
    """Duck-typed ``weatherrouting.Grib`` over our weather grid.

    Returns ``(twd deg, tws m/s)`` — the units libweatherrouting expects.
    Temporal scope is honest: queries beyond the forecast horizon return
    ``None`` (no data is no data; the library then ends the route, and the
    adapter turns that into a partial route). Geographic scope clamps to
    the grid edges — the same policy as the in-repo sampler, and a
    necessity here: the library's isochrone envelope spreads past the
    route corridor, and it treats a mid-search ``None`` as an error.
    """

    def __init__(self, grid: WeatherGrid, epoch: datetime) -> None:
        self._grid = grid
        self._epoch = epoch

    def get_wind_at(self, t: Any, lat: Any, lon: Any) -> tuple[float, float] | None:
        """Wind at (datetime t, lat, lon) as (direction-from deg, speed m/s)."""
        hours = (t - self._epoch).total_seconds() / 3600.0
        grid = self._grid
        if not (grid.times[0] <= hours <= grid.times[-1]):
            return None
        speed_kt, direction_deg = grid.wind(
            np.array([hours]),
            np.array([np.clip(float(lat), grid.lats[0], grid.lats[-1])]),
            np.array([np.clip(float(lon), grid.lons[0], grid.lons[-1])]),
        )
        return float(direction_deg[0]), float(speed_kt[0]) / KT_PER_MS


def _import_weatherrouting() -> Any:
    """Import libweatherrouting lazily, with an actionable error message."""
    try:
        import weatherrouting
    except ImportError as exc:  # pragma: no cover - environment dependent
        raise ImportError(
            "libweatherrouting requires the optional 'oracle' dependency "
            "group (PyPI package 'weatherrouting', GPLv3): run "
            "`uv sync --group oracle`"
        ) from exc
    return weatherrouting


def _write_lib_polar(polar: PolarTable, path: Path) -> None:
    """Write our polar in libweatherrouting's tab-separated format.

    Layout: first line ``TWA\\TWS`` followed by TWS values (kt), then one
    row per TWA (deg) with boat speeds (kt) — the same table content as our
    OpenCPN-style polar CSV, different delimiters.
    """
    lines = ["TWA\\TWS\t" + "\t".join(f"{v:g}" for v in polar.tws)]
    for j, angle in enumerate(polar.twa):
        lines.append("\t".join([f"{angle:g}"] + [f"{v:g}" for v in polar.speed[:, j]]))
    path.write_text("\n".join(lines) + "\n")


@dataclass
class LibWeatherRoutingRouter:
    """Router adapter over libweatherrouting's LinearBestIsoRouter.

    Satisfies the :class:`~light_router.routing.protocol.Router` protocol
    structurally (no inheritance from library code). The GPLv3 package is
    imported inside :meth:`route` only, so importing this module is safe in
    any environment.
    """

    weather: xr.Dataset | None = field(default=None, kw_only=True)
    """Canonical CF weather dataset for the passage (Compatibility rule 1);
    bound by :meth:`for_weather`, None until then."""

    polar: PolarTable
    """Boat polar, converted to the library's polar format per run."""

    config: LibWeatherRoutingConfig = field(default_factory=LibWeatherRoutingConfig)
    """Tuning surface for the library's isochrone search."""

    start_datetime: datetime | None = None
    """Calendar time of weather hour 0 (UTC); None means the synthetic
    epoch (``experiments.synthetic.SYNTHETIC_EPOCH``)."""

    @property
    def name(self) -> str:
        """Adapter identity: the measured version of the wrapped package."""
        version = metadata.version(LIBWEATHERROUTING_PACKAGE)
        return f"libweatherrouting@{version}"

    def for_weather(self, weather: xr.Dataset) -> LibWeatherRoutingRouter:
        """Bind this oracle setup to a weather dataset (plain replace)."""
        return replace(self, weather=weather)

    def route(
        self,
        start: tuple[float, float],
        finish: tuple[float, float],
        start_time: float = 0.0,
    ) -> Route:
        """Route through libweatherrouting, stepping until arrival.

        ``start_time`` is the departure in hours since weather hour 0. The
        returned Route carries the library's full track (one waypoint per
        isochrone level); wind along it is sampled downstream. ``reached`` is
        False when the horizon was exhausted, when the departure falls
        outside the forecast's time coverage, or when the search ran out
        of weather mid-route (the library's ``RoutingNoWindError``) — in
        every case the route is the honest partial track, never invented
        geometry.
        """
        if self.weather is None:
            raise RuntimeError(
                "libweatherrouting oracle router is not bound to weather yet; "
                "call for_weather(weather) first"
            )
        weatherrouting = _import_weatherrouting()
        from weatherrouting.routers.linearbestisorouter import (
            LinearBestIsoRouter,
        )

        cfg = self.config
        grid = grid_from_dataset(self.weather)
        if not (
            grid.times[0] <= start_time and start_time + cfg.dt_hours <= grid.times[-1]
        ):
            return self._route_from_path([], start, start_time, reached=False)

        epoch = (
            self.start_datetime if self.start_datetime is not None else SYNTHETIC_EPOCH
        )
        departure = epoch + timedelta(hours=start_time)

        with tempfile.TemporaryDirectory(prefix="lr-libweatherrouting-") as tmp:
            polar_file = Path(tmp) / "polar.txt"
            _write_lib_polar(self.polar, polar_file)
            routing = weatherrouting.Routing(
                LinearBestIsoRouter,
                weatherrouting.Polar(str(polar_file)),
                [start, finish],
                _GridGrib(grid, epoch),
                departure,
            )
            routing.algorithm.set_param_value("min_increase", cfg.min_increase_nm)
            routing.algorithm.set_param_value("subdiv", cfg.subdiv)
            routing.algorithm.set_param_value("concurrent", False)

            result = None
            while not routing.end:
                try:
                    result = routing.step(cfg.dt_hours)
                except weatherrouting.RoutingNoWindError:
                    break  # search ran out of weather: partial route below
                elapsed = (result.time - departure).total_seconds() / 3600.0
                if elapsed > cfg.max_hours:
                    break  # horizon exhausted: partial route below

        path = list(result.path) if result is not None else []
        return self._route_from_path(path, start, start_time, reached=routing.end)

    def _route_from_path(
        self,
        path: list[Any],
        start: tuple[float, float],
        start_time: float,
        reached: bool,
    ) -> Route:
        """Convert the library's IsoPoint track into a Route.

        The library's first isochrone point is the start itself with
        placeholder wind/speed values; per Route semantics those become NaN
        at the start waypoint.
        """
        if not path:
            return Route(
                waypoints=[Waypoint(lat=start[0], lon=start[1], time=start_time)],
                reached=False,
            )

        epoch = (
            self.start_datetime if self.start_datetime is not None else SYNTHETIC_EPOCH
        )
        did_reach = bool(reached and len(path) >= 2)
        return Route(
            waypoints=[
                Waypoint(
                    lat=float(p.pos[0]),
                    lon=float(p.pos[1]),
                    time=(p.time - epoch).total_seconds() / 3600.0,
                )
                for p in path
            ],
            reached=did_reach,
        )
