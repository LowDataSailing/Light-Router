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

from dataclasses import dataclass
from typing import Any

import numpy as np
import xarray as xr

from light_router.geo import destination, great_circle_distance
from light_router.models.route import Route, Waypoint
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

    The router's tuning lives in its own attributes below — every router
    carries its config this way, so a router instance is its single,
    complete setup.
    """

    grid: WeatherGrid
    """Weather grid the router plans against."""

    polar: PolarTable
    """Boat polar: speed as a function of wind speed and angle."""

    dt_hours: float = 1.0
    """Isochrone time step (h) — one expansion level per step."""

    n_headings: int = 36  # every 10 degrees
    """Candidate headings tried from each point, every level."""

    bin_deg: float = 1.0
    """Geographic pruning bin size (deg) — one survivor per bin."""

    max_points: int = 1500
    """Cap on candidate points per level, after pruning."""

    finish_radius_nm: float = 25.0
    """Arrival radius around the finish (nm)."""

    max_hours: float = 240.0
    """Planning horizon (h); a route that cannot finish within it is
    returned as partial (``reached`` is False)."""

    min_speed_kt: float = 0.1
    """Candidates the polar cannot sail faster than are dropped
    (dead calm / head wind)."""

    name = "isochrone-surrogate"
    """Algorithm identity for run manifests — not the oracle
    (Decision #15); validated against it before results depend on it."""

    @classmethod
    def from_dataset(
        cls,
        weather: xr.Dataset,
        polar: PolarTable,
        **kwargs: Any,
    ) -> IsochroneRouter:
        """Build the router from the canonical CF weather Dataset.

        Args:
            weather: Weather as the canonical CF Dataset.
            polar: Boat polar table.
            **kwargs: Tuning overrides for the router's own config
                attributes (``dt_hours``, ``n_headings``, ...).
        """
        from light_router.dataset import grid_from_dataset

        return cls(grid=grid_from_dataset(weather), polar=polar, **kwargs)

    def config_as_dict(self) -> dict[str, float | int]:
        """Plain-dict form of the tuning attributes, for manifests.

        Every tuning field is included, so a manifest fully determines the
        router configuration.
        """
        return {
            "dt_hours": self.dt_hours,
            "n_headings": self.n_headings,
            "bin_deg": self.bin_deg,
            "max_points": self.max_points,
            "finish_radius_nm": self.finish_radius_nm,
            "max_hours": self.max_hours,
            "min_speed_kt": self.min_speed_kt,
        }

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
        headings = np.arange(self.n_headings, dtype=float) * (360.0 / self.n_headings)

        if (
            float(great_circle_distance(start[0], start[1], finish[0], finish[1]))
            <= self.finish_radius_nm
        ):
            return self._empty_route(start, start_time)

        levels: list[_Level] = []
        current = _Level(
            lat=np.array([start[0]]),
            lon=np.array([start[1]]),
            parent=np.array([-1]),
        )
        t = start_time
        while t - start_time <= self.max_hours:
            t_next = t + self.dt_hours

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

            kept = self._prune(candidates.lat, candidates.lon, remaining)
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
        tws, wdir = self.grid.wind(
            np.full(len(current.lat), t), current.lat, current.lon
        )

        # (n_points, n_headings) candidate arrays
        twa = np.abs(headings[None, :] - wdir[:, None])
        twa = np.where(twa > 180.0, 360.0 - twa, twa)
        speed = np.asarray(
            self.polar.boat_speed(np.repeat(tws[:, None], len(headings), axis=1), twa)
        )
        dist = speed * self.dt_hours
        sail = speed > self.min_speed_kt

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
        if remaining[idx] <= self.finish_radius_nm:
            return idx
        return None

    def _prune(
        self, lat: np.ndarray, lon: np.ndarray, remaining: np.ndarray
    ) -> np.ndarray:
        """Keep the best-progressing candidate per geographic bin."""
        bin_lat = np.floor(lat / self.bin_deg).astype(np.int64)
        bin_lon = np.floor(lon / self.bin_deg).astype(np.int64)
        key = bin_lat * 100000 + bin_lon
        order = np.lexsort((remaining, key))  # sort by key, then remaining
        key_sorted = key[order]
        first = np.ones(len(order), dtype=bool)
        first[1:] = key_sorted[1:] != key_sorted[:-1]
        kept = order[first]
        if len(kept) > self.max_points:
            kept = kept[np.argsort(remaining[kept])[: self.max_points]]
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
        """Rebuild the route ending at ``levels[level_no][point_idx]``.

        The expansion only ever moves forward: each level stores its
        candidate points plus, for each, the index of the *parent* point
        in the previous level it was reached from. So the route is not
        known during the expansion — only the best endpoint is. This
        walks the parent chain backwards from that endpoint:

        1. take the arrival (or closest) point at ``levels[level_no]``;
        2. jump to its parent in the previous level, and to that point's
           parent, and so on — each hop is one isochrone time step back;
        3. the chain ends at the start (parent index -1), which is
           prepended;
        4. the collected points are reversed into sailing order, and each
           gets its time: start time plus one ``dt_hours`` per level.

        The result is the optimal path through the pruned tree — the
        points that survived pruning because they were the best
        progress-makers in their geographic bin at their time.
        """
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
        time = start_time + np.arange(n) * self.dt_hours
        return Route(
            waypoints=[
                Waypoint(lat=float(la), lon=float(lo), time=float(ti))
                for la, lo, ti in zip(lat, lon, time)
            ],
            reached=reached,
        )

    def _empty_route(self, start: tuple[float, float], start_time: float) -> Route:
        """Trivial route for a start already inside the finish radius."""
        return Route(
            waypoints=[Waypoint(start[0], start[1], start_time)],
            reached=True,
        )
