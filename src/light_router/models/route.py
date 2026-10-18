"""Route and router configuration: the plan a router returns.

``Route`` is the interface's return type (Compatibility rule 2): every
router — the in-repo isochrone surrogate and the oracle subprocess —
produces one. A route is a suite of :class:`Waypoint` (the maritime
ontology: positions with times); every geometric quantity (headings,
leg speeds, distances) is derived from it, and the weather along a route
is sampled where needed via :mod:`light_router.sampling` — a router
outputs a plan, never weather beliefs (Decision #22). Each router
carries its own tuning as its attributes; the helpers summarize a route
for metrics and reporting.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from light_router.geo import great_circle_distance, initial_bearing


@dataclass
class Waypoint:
    """One point of a route: where the boat is, and when."""

    lat: float
    """Latitude (deg)."""

    lon: float
    """Longitude (deg)."""

    time: float
    """Hours since the scenario start."""


@dataclass
class Route:
    """Computed route: a suite of waypoints plus the arrival flag.

    The waypoints are the router's entire output. Per-waypoint arrays
    (:attr:`lat`, :attr:`lon`, :attr:`time`) and leg properties
    (:attr:`heading`, :attr:`speed`) are derived views over them, and so
    are the route scalars: the arrival time is the final waypoint's time
    and the distance is the sum of the legs. The wind along the route is
    not stored — sample it from the weather the route was planned
    against (or sailed on) via
    :func:`light_router.sampling.wind_along_route`.
    """

    waypoints: list[Waypoint]
    """The route's waypoints, in sailing order."""

    reached: bool
    """Whether the route entered the finish radius within the horizon
    (the one fact the geometry cannot tell: a partial route still ends
    somewhere)."""

    @property
    def n_waypoints(self) -> int:
        return len(self.waypoints)

    @property
    def eta_hours(self) -> float:
        """Arrival time (h since scenario start) — the final waypoint's
        time; NaN when the route did not reach the finish."""
        if not self.reached or not self.waypoints:
            return float("nan")
        return float(self.waypoints[-1].time)

    @property
    def distance_nm(self) -> float:
        """Total sailed distance (nm) — the sum of the leg distances."""
        if self.n_waypoints < 2:
            return 0.0
        lat, lon = self.lat, self.lon
        return float(
            np.sum(great_circle_distance(lat[:-1], lon[:-1], lat[1:], lon[1:]))
        )

    @property
    def lat(self) -> np.ndarray:
        """Waypoint latitudes (deg), length ``n_waypoints``."""
        return np.array([w.lat for w in self.waypoints], dtype=float)

    @property
    def lon(self) -> np.ndarray:
        """Waypoint longitudes (deg), length ``n_waypoints``."""
        return np.array([w.lon for w in self.waypoints], dtype=float)

    @property
    def time(self) -> np.ndarray:
        """Hours since the scenario start, one per waypoint."""
        return np.array([w.time for w in self.waypoints], dtype=float)

    @property
    def heading(self) -> np.ndarray:
        """Heading of the leg arriving at each waypoint (deg true); NaN at
        the start waypoint (no leg arrives there)."""
        n = self.n_waypoints
        out = np.full(n, np.nan)
        if n >= 2:
            lat, lon = self.lat, self.lon
            out[1:] = initial_bearing(lat[:-1], lon[:-1], lat[1:], lon[1:])
        return out

    @property
    def speed(self) -> np.ndarray:
        """Speed over ground of the leg arriving at each waypoint (kt);
        NaN at the start waypoint. With no currents (Level 1) this is the
        polar speed the router planned at."""
        n = self.n_waypoints
        out = np.full(n, np.nan)
        if n >= 2:
            lat, lon, time = self.lat, self.lon, self.time
            dist = great_circle_distance(lat[:-1], lon[:-1], lat[1:], lon[1:])
            dt = time[1:] - time[:-1]
            out[1:] = np.where(dt > 0, dist / dt, np.nan)
        return out


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
