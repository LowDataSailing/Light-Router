"""Route and router configuration: the plan a router returns.

``Route`` is the interface's return type (Compatibility rule 2): every
router — the in-repo isochrone surrogate and the future oracle subprocess —
produces one. ``RouterConfig`` is the shared tuning surface; the helpers
summarize a route for metrics and reporting.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from light_router.geo import great_circle_distance


@dataclass
class Route:
    """Computed route: parallel per-waypoint arrays plus route-level scalars."""

    lat: np.ndarray
    """Waypoint latitudes (deg), length ``n_waypoints``."""

    lon: np.ndarray
    """Waypoint longitudes (deg), length ``n_waypoints``."""

    time: np.ndarray
    """Hours since the scenario start, one per waypoint."""

    heading: np.ndarray
    """Heading per waypoint (deg true); NaN at the start waypoint."""

    speed: np.ndarray
    """Boat speed per waypoint (kt, polar speed — no currents at Level 1)."""

    tws: np.ndarray
    """True wind speed per waypoint (kt)."""

    twa: np.ndarray
    """True wind angle per waypoint (deg): the absolute angle between
    heading and wind direction (0 = dead upwind, 180 = dead downwind)."""

    reached: bool
    """Whether the route entered the finish radius within the horizon."""

    eta_hours: float
    """Arrival time (h since scenario start); NaN when not reached."""

    distance_nm: float
    """Total sailed distance (nm)."""

    @property
    def n_waypoints(self) -> int:
        return len(self.lat)


@dataclass
class RouterConfig:
    """Shared tuning surface for the isochrone router."""

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
