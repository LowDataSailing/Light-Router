"""Time-stepped isochrone router (Level 1 baseline).

From each reachable point at time t, expand candidate headings, move each
candidate by its polar speed over one time step, prune dominated points by
geographic bin, and repeat until a point reaches the finish. The route is
reconstructed by backtracking parent pointers.

No land avoidance, no currents — Level 1 per the Baseline System spec.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

import numpy as np
import xarray as xr

from .geo import destination, great_circle_distance
from .polar import PolarTable
from .weather import WeatherGrid


@dataclass
class Route:
    """Computed route. Times are hours since the scenario start."""

    lat: np.ndarray
    lon: np.ndarray
    time: np.ndarray
    heading: np.ndarray
    speed: np.ndarray
    tws: np.ndarray
    twa: np.ndarray
    reached: bool
    eta_hours: float
    distance_nm: float

    @property
    def n_waypoints(self) -> int:
        return len(self.lat)


@dataclass
class _Level:
    """Candidate points at one isochrone level."""

    lat: np.ndarray
    lon: np.ndarray
    parent: np.ndarray  # index into the previous level
    heading: np.ndarray
    speed: np.ndarray
    tws: np.ndarray
    twa: np.ndarray


@dataclass
class RouterConfig:
    dt_hours: float = 1.0
    n_headings: int = 36  # every 10 degrees
    bin_deg: float = 1.0  # geographic pruning bin size
    max_points: int = 1500  # per level, after pruning
    finish_radius_nm: float = 25.0
    max_hours: float = 240.0
    min_speed_kt: float = 0.1  # below this a candidate cannot sail


@runtime_checkable
class Router(Protocol):
    """The routing interface every router implements (Compatibility rule 2).

    ``route(start, finish, start_time) -> Route`` is the entire contract: the
    Level 1 oracle must be replaceable by an external reference router (a
    pinned subprocess adapter) without changing the harness. A router is
    bound to its weather at construction — see the router factory in
    ``staircase.run_staircase``.
    """

    def route(
        self,
        start: tuple[float, float],
        finish: tuple[float, float],
        start_time: float = 0.0,
    ) -> Route: ...


@dataclass
class IsochroneRouter:
    """The provisional in-process surrogate oracle.

    Fast numpy isochrone engine used inside harness loops; validated against
    the industry reference router before any reported result depends on it
    (Decision #15). Not the oracle itself.
    """

    grid: WeatherGrid
    polar: PolarTable
    config: RouterConfig = field(default_factory=RouterConfig)

    @classmethod
    def from_dataset(
        cls,
        weather: xr.Dataset,
        polar: PolarTable,
        config: RouterConfig | None = None,
    ) -> IsochroneRouter:
        """Build the router from the canonical CF weather Dataset."""
        from .dataset import grid_from_dataset

        return cls(
            grid=grid_from_dataset(weather),
            polar=polar,
            config=config if config is not None else RouterConfig(),
        )

    def route(
        self,
        start: tuple[float, float],
        finish: tuple[float, float],
        start_time: float = 0.0,
    ) -> Route:
        """Compute the route from start to finish, departing at start_time.

        Returns a reached route as soon as a candidate enters the finish
        radius, or the partial route to the closest reached point if the
        time horizon is exhausted (Route.reached is False).
        """
        cfg = self.config
        headings = np.arange(cfg.n_headings, dtype=float) * (360.0 / cfg.n_headings)

        start_lat = np.array([start[0]])
        start_lon = np.array([start[1]])
        if (
            float(great_circle_distance(start[0], start[1], finish[0], finish[1]))
            <= cfg.finish_radius_nm
        ):
            return self._empty_route(start, start_time)

        levels: list[_Level] = []
        current = _Level(
            lat=start_lat,
            lon=start_lon,
            parent=np.array([-1]),
            heading=np.array([np.nan]),
            speed=np.array([np.nan]),
            tws=np.array([np.nan]),
            twa=np.array([np.nan]),
        )
        t = start_time
        while t - start_time <= cfg.max_hours:
            t_next = t + cfg.dt_hours
            tws, wdir = self.grid.wind(
                np.full(len(current.lat), t), current.lat, current.lon
            )

            # (n_points, n_headings) candidate arrays
            twa = np.abs(headings[None, :] - wdir[:, None])
            twa = np.where(twa > 180.0, 360.0 - twa, twa)
            speed = np.asarray(
                self.polar.boat_speed(
                    np.repeat(tws[:, None], len(headings), axis=1), twa
                )
            )
            dist = speed * cfg.dt_hours
            sail = speed > cfg.min_speed_kt

            lat_c = np.repeat(current.lat[:, None], len(headings), axis=1)
            lon_c = np.repeat(current.lon[:, None], len(headings), axis=1)
            new_lat, new_lon = destination(lat_c, lon_c, headings[None, :], dist)
            new_lat, new_lon = np.asarray(new_lat), np.asarray(new_lon)

            flat_lat = new_lat[sail]
            flat_lon = new_lon[sail]
            if flat_lat.size == 0:
                break  # trapped (e.g., dead calm everywhere)
            flat_parent = np.repeat(np.arange(len(current.lat)), len(headings))[
                sail.ravel()
            ]
            flat_heading = np.tile(headings, len(current.lat))[sail.ravel()]
            flat_speed = speed[sail]
            flat_tws = np.repeat(tws[:, None], len(headings), axis=1)[sail]
            flat_twa = twa[sail]

            remaining = np.asarray(
                great_circle_distance(flat_lat, flat_lon, finish[0], finish[1])
            )
            reached_idx = int(np.argmin(remaining))
            if remaining[reached_idx] <= cfg.finish_radius_nm:
                levels.append(
                    _Level(
                        flat_lat,
                        flat_lon,
                        flat_parent,
                        flat_heading,
                        flat_speed,
                        flat_tws,
                        flat_twa,
                    )
                )
                return self._backtrack(
                    levels, reached_idx, start, start_time, reached=True
                )

            kept = self._prune(flat_lat, flat_lon, remaining, cfg)
            # Store the pruned level: candidate parents of the next level index
            # into this pruned array.
            levels.append(
                _Level(
                    flat_lat[kept],
                    flat_lon[kept],
                    flat_parent[kept],
                    flat_heading[kept],
                    flat_speed[kept],
                    flat_tws[kept],
                    flat_twa[kept],
                )
            )
            current = levels[-1]
            t = t_next

        # Horizon exhausted: return the partial route to the closest reached point.
        best_level, best_idx = self._closest_point(levels, finish)
        route = self._backtrack(levels, best_idx, start, start_time, reached=False)
        return route

    def _prune(
        self, lat: np.ndarray, lon: np.ndarray, remaining: np.ndarray, cfg: RouterConfig
    ) -> np.ndarray:
        """Keep the best-progressing candidate per geographic bin."""
        bin_lat = np.floor(lat / cfg.bin_deg).astype(np.int64)
        bin_lon = np.floor(lon / cfg.bin_deg).astype(np.int64)
        key = bin_lat * 100000 + bin_lon
        order = np.lexsort((remaining, key))  # sort by key, then remaining
        key_sorted = key[order]
        first = np.ones(len(order), dtype=bool)
        first[1:] = key_sorted[1:] != key_sorted[:-1]
        kept = order[first]
        if len(kept) > cfg.max_points:
            kept = kept[np.argsort(remaining[kept])[: cfg.max_points]]
        return kept

    def _closest_point(
        self, levels: list[_Level], finish: tuple[float, float]
    ) -> tuple[int, int]:
        best_level, best_idx, best_dist = 0, 0, np.inf
        for li, level in enumerate(levels):
            dist = np.asarray(
                great_circle_distance(level.lat, level.lon, finish[0], finish[1])
            )
            idx = int(np.argmin(dist))
            if float(dist[idx]) < best_dist:
                best_level, best_idx, best_dist = li, idx, float(dist[idx])
        return best_level, best_idx

    def _backtrack(
        self,
        levels: list[_Level],
        level_idx: int,
        start: tuple[float, float],
        start_time: float,
        reached: bool,
    ) -> Route:
        lats, lons, headings, speeds, twss, twas = [], [], [], [], [], []
        idx = level_idx
        for level in reversed(levels[: level_idx + 1]):
            lats.append(level.lat[idx])
            lons.append(level.lon[idx])
            headings.append(level.heading[idx])
            speeds.append(level.speed[idx])
            twss.append(level.tws[idx])
            twas.append(level.twa[idx])
            idx = int(level.parent[idx])
        lats.append(start[0])
        lons.append(start[1])
        headings.append(np.nan)
        speeds.append(np.nan)
        twss.append(np.nan)
        twas.append(np.nan)

        lat = np.array(lats[::-1], dtype=float)
        lon = np.array(lons[::-1], dtype=float)
        heading = np.array(headings[::-1], dtype=float)
        speed = np.array(speeds[::-1], dtype=float)
        tws = np.array(twss[::-1], dtype=float)
        twa = np.array(twas[::-1], dtype=float)
        n = len(lat)
        time = start_time + np.arange(n) * self.config.dt_hours
        distance = float(
            np.sum(great_circle_distance(lat[:-1], lon[:-1], lat[1:], lon[1:]))
        )
        eta = float(time[-1]) if reached else float("nan")
        return Route(
            lat=lat,
            lon=lon,
            time=time,
            heading=heading,
            speed=speed,
            tws=tws,
            twa=twa,
            reached=reached,
            eta_hours=eta,
            distance_nm=distance,
        )

    def _empty_route(self, start: tuple[float, float], start_time: float) -> Route:
        return Route(
            lat=np.array([start[0]]),
            lon=np.array([start[1]]),
            time=np.array([start_time]),
            heading=np.array([np.nan]),
            speed=np.array([np.nan]),
            tws=np.array([np.nan]),
            twa=np.array([np.nan]),
            reached=True,
            eta_hours=start_time,
            distance_nm=0.0,
        )


def route_bearing(route: Route) -> float:
    """Initial bearing of the first sailing leg (deg), NaN for empty routes."""
    if route.n_waypoints < 2:
        return float("nan")
    for i in range(route.n_waypoints - 1):
        if not np.isnan(route.heading[i + 1]):
            return float(route.heading[i + 1])
    return float("nan")


def mean_vmg(route: Route, finish: tuple[float, float]) -> float:
    """Mean velocity-made-good toward the finish (kt)."""
    if route.n_waypoints < 2:
        return 0.0
    total_time = float(route.time[-1] - route.time[0])
    if total_time <= 0:
        return 0.0
    progress = float(
        great_circle_distance(route.lat[0], route.lon[0], finish[0], finish[1])
        - great_circle_distance(route.lat[-1], route.lon[-1], finish[0], finish[1])
    )
    return progress / total_time
