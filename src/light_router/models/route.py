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
class RouterConfig:
    dt_hours: float = 1.0
    n_headings: int = 36  # every 10 degrees
    bin_deg: float = 1.0  # geographic pruning bin size
    max_points: int = 1500  # per level, after pruning
    finish_radius_nm: float = 25.0
    max_hours: float = 240.0
    min_speed_kt: float = 0.1  # below this a candidate cannot sail

    def as_dict(self) -> dict[str, float | int]:
        """Plain-dict form for manifests and other serialized output."""
        return {
            "dt_hours": self.dt_hours,
            "n_headings": self.n_headings,
            "bin_deg": self.bin_deg,
            "max_points": self.max_points,
            "finish_radius_nm": self.finish_radius_nm,
            "max_hours": self.max_hours,
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
