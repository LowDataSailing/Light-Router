"""Time-stepped isochrone router: the provisional in-process surrogate.

From each reachable point at time t, expand candidate headings, move each
candidate by its polar speed over one time step, prune dominated points by
geographic bin, and repeat until a point reaches the finish. The route is
reconstructed by backtracking parent pointers into a suite of waypoints —
the router outputs the plan only; weather along it is sampled downstream
(Decision #22).

This module is the in-repo adapter over the Router seam
(``light_router.routing.protocol``); the industry oracle subprocess is the
second adapter (Decision #15). No land avoidance, no currents — Level 1 per
the Baseline System spec.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import xarray as xr

from light_router.geo import destination, great_circle_distance
from light_router.models.route import Route, RouterConfig, Waypoint
from light_router.models.vessel import PolarTable
from light_router.models.weather import WeatherGrid
from light_router.routing.protocol import BaseRouter


@dataclass
class _Level:
    """Candidate points at one isochrone level."""

    lat: np.ndarray
    lon: np.ndarray
    parent: np.ndarray  # index into the previous level


@dataclass
class IsochroneRouter(BaseRouter):
    """The provisional in-process surrogate oracle.

    Fast numpy isochrone engine used inside harness loops; validated against
    the industry reference router before any reported result depends on it
    (Decision #15). Not the oracle itself. Inherits ``BaseRouter`` so the
    contract is fixed nominally; future in-repo algorithms subclass
    ``BaseRouter`` the same way instead of re-deriving the interface.
    """

    grid: WeatherGrid
    polar: PolarTable
    config: RouterConfig = field(default_factory=RouterConfig)

    name = "isochrone-surrogate"
    """Algorithm identity for run manifests — not the oracle
    (Decision #15); validated against it before results depend on it."""

    @classmethod
    def from_dataset(
        cls,
        weather: xr.Dataset,
        polar: PolarTable,
        config: RouterConfig | None = None,
    ) -> IsochroneRouter:
        """Build the router from the canonical CF weather Dataset."""
        from light_router.dataset import grid_from_dataset

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

        if (
            float(great_circle_distance(start[0], start[1], finish[0], finish[1]))
            <= cfg.finish_radius_nm
        ):
            return self._empty_route(start, start_time)

        levels: list[_Level] = []
        current = _Level(
            lat=np.array([start[0]]),
            lon=np.array([start[1]]),
            parent=np.array([-1]),
        )
        t = start_time
        while t - start_time <= cfg.max_hours:
            t_next = t + cfg.dt_hours

            candidates = self._expand(current, headings, t)
            if candidates.lat.size == 0:
                break  # trapped (e.g., dead calm everywhere)

            remaining = np.asarray(
                great_circle_distance(
                    candidates.lat, candidates.lon, finish[0], finish[1]
                )
            )
            reached_idx = self._arrival(remaining)
            if reached_idx is not None:
                levels.append(candidates)
                return self._backtrack(
                    levels,
                    len(levels) - 1,
                    reached_idx,
                    start,
                    start_time,
                    reached=True,
                )

            kept = self._prune(candidates.lat, candidates.lon, remaining, cfg)
            # Store the pruned level: candidate parents of the next level index
            # into this pruned array.
            levels.append(
                _Level(
                    candidates.lat[kept],
                    candidates.lon[kept],
                    candidates.parent[kept],
                )
            )
            current = levels[-1]
            t = t_next

        # Horizon exhausted: return the partial route to the closest reached point.
        best_level, best_idx = self._closest_point(levels, finish)
        return self._backtrack(
            levels, best_level, best_idx, start, start_time, reached=False
        )

    def _expand(self, current: _Level, headings: np.ndarray, t: float) -> _Level:
        """One isochrone expansion: every candidate reachable at t + dt.

        Samples the wind at each frontier point, evaluates the polar for
        every (point, heading) pair, moves each sailable candidate along
        its heading, and returns the flat candidate arrays with parent
        indices into ``current``.
        """
        cfg = self.config
        tws, wdir = self.grid.wind(
            np.full(len(current.lat), t), current.lat, current.lon
        )

        # (n_points, n_headings) candidate arrays
        twa = np.abs(headings[None, :] - wdir[:, None])
        twa = np.where(twa > 180.0, 360.0 - twa, twa)
        speed = np.asarray(
            self.polar.boat_speed(np.repeat(tws[:, None], len(headings), axis=1), twa)
        )
        dist = speed * cfg.dt_hours
        sail = speed > cfg.min_speed_kt

        lat_c = np.repeat(current.lat[:, None], len(headings), axis=1)
        lon_c = np.repeat(current.lon[:, None], len(headings), axis=1)
        new_lat, new_lon = destination(lat_c, lon_c, headings[None, :], dist)
        new_lat, new_lon = np.asarray(new_lat), np.asarray(new_lon)

        return _Level(
            lat=new_lat[sail],
            lon=new_lon[sail],
            parent=np.repeat(np.arange(len(current.lat)), len(headings))[sail.ravel()],
        )

    def _arrival(self, remaining: np.ndarray) -> int | None:
        """Index of the candidate closest to the finish, if it is inside the
        finish radius — checking the closest is sufficient: if it is not
        inside, nothing is."""
        idx = int(np.argmin(remaining))
        if remaining[idx] <= self.config.finish_radius_nm:
            return idx
        return None

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
        """Level and index of the candidate that came closest to the finish."""
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
        level_no: int,
        point_idx: int,
        start: tuple[float, float],
        start_time: float,
        reached: bool,
    ) -> Route:
        """Rebuild the route ending at ``levels[level_no][point_idx]``."""
        lats, lons = [], []
        idx = point_idx
        for level in reversed(levels[: level_no + 1]):
            lats.append(level.lat[idx])
            lons.append(level.lon[idx])
            idx = int(level.parent[idx])
        lats.append(start[0])
        lons.append(start[1])

        lat = np.array(lats[::-1], dtype=float)
        lon = np.array(lons[::-1], dtype=float)
        n = len(lat)
        time = start_time + np.arange(n) * self.config.dt_hours
        distance = float(
            np.sum(great_circle_distance(lat[:-1], lon[:-1], lat[1:], lon[1:]))
        )
        eta = float(time[-1]) if reached else float("nan")
        waypoints = [
            Waypoint(lat=float(la), lon=float(lo), time=float(ti))
            for la, lo, ti in zip(lat, lon, time)
        ]
        return Route(
            waypoints=waypoints,
            reached=reached,
            eta_hours=eta,
            distance_nm=distance,
        )

    def _empty_route(self, start: tuple[float, float], start_time: float) -> Route:
        """Trivial route for a start already inside the finish radius."""
        return Route(
            waypoints=[Waypoint(start[0], start[1], start_time)],
            reached=True,
            eta_hours=start_time,
            distance_nm=0.0,
        )
