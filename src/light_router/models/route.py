"""Route and router configuration: the plan a router returns.

``Route`` is the interface's return type (Compatibility rule 2): every
router — the in-repo isochrone surrogate and the oracle subprocess —
produces one. A route is a suite of :class:`Waypoint` (the maritime
ontology: positions with times); every geometric quantity (headings,
leg speeds, distances) is derived from it, and the weather along a route
is sampled where needed via :mod:`light_router.sampling` — a router
outputs a plan, never weather beliefs (Decision #22). ``RouterConfig``
is the isochrone router's own tuning surface; the helpers summarize a
route for metrics and reporting.
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
    """Computed route: a suite of waypoints plus route-level scalars.

    The waypoints are the router's entire output. Per-waypoint arrays
    (:attr:`lat`, :attr:`lon`, :attr:`time`) and leg properties
    (:attr:`heading`, :attr:`speed`) are derived views over them; the
    wind along the route is not stored — sample it from the weather the
    route was planned against (or sailed on) via
    :func:`light_router.sampling.wind_along_route`.
    """

    waypoints: list[Waypoint]
    """The route's waypoints, in sailing order."""

    reached: bool
    """Whether the route entered the finish radius within the horizon."""

    eta_hours: float
    """Arrival time (h since scenario start); NaN when not reached."""

    distance_nm: float
    """Total sailed distance (nm)."""

    @property
    def n_waypoints(self) -> int:
        return len(self.waypoints)

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


@dataclass
class RouterConfig:
    """Tuning surface of the isochrone router (its own config — other
    routers carry theirs as their own attributes)."""

    dt_hours: float = 1.0
    """Isochrone time step (h) — one expansion level per step."""

    n_headings: int = 36  # every 10 degrees
    """Candidate headings tried from each point, every level."""

    bin_deg: float = 1.0  # geographic pruning bin size
    """Geographic pruning bin size (deg) — one survivor per bin."""

    max_points: int = 1500  # per level, after pruning
    """Cap on candidate points per level, after pruning."""

    finish_radius_nm: float = 25.0
    """Arrival radius around the finish (nm)."""

    max_hours: float = 240.0
    """Planning horizon (h); a route that cannot finish within it is
    returned as partial (``reached`` is False)."""

    min_speed_kt: float = 0.1  # below this a candidate cannot sail
    """Candidates the polar cannot sail faster than are dropped
    (dead calm / head wind)."""

    def as_dict(self) -> dict[str, float | int]:
        """Plain-dict form for manifests and other serialized output.

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
