"""Route-quality metrics: degraded route vs the Level 1 reference route.

All metrics are reported separately, never combined into one score.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict

import numpy as np

from .geo import great_circle_distance
from .isochrone import Route, mean_vmg, route_bearing

DECISION_SPLIT_DEG = 15.0  # initial-bearing split that counts as a different decision


@dataclass
class RouteMetrics:
    eta_diff_pct: float
    distance_diff_pct: float
    vmg_diff_kt: float
    max_wind_diff_kt: float
    decision_divergence: bool
    initial_bearing_diff_deg: float
    geographic_divergence_nm: float
    reached: bool

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


def _max_wind(route: Route) -> float:
    sailing = route.tws[~np.isnan(route.tws)]
    return float(np.max(sailing)) if sailing.size else 0.0


def _track_divergence(a: Route, b: Route, n_samples: int = 50) -> float:
    """Mean nearest-neighbour distance from track a to track b (nm), both
    resampled to a common index. Asymmetric on purpose: how far the degraded
    route drifts from the reference."""
    if a.n_waypoints < 2 or b.n_waypoints < 2:
        return 0.0
    ta = np.linspace(0.0, 1.0, n_samples)
    a_lat = np.interp(ta, np.linspace(0.0, 1.0, a.n_waypoints), a.lat)
    a_lon = np.interp(ta, np.linspace(0.0, 1.0, a.n_waypoints), a.lon)
    b_lat = np.interp(ta, np.linspace(0.0, 1.0, b.n_waypoints), b.lat)
    b_lon = np.interp(ta, np.linspace(0.0, 1.0, b.n_waypoints), b.lon)
    dist = great_circle_distance(a_lat, a_lon, b_lat, b_lon)
    return float(np.mean(dist))


def compare_routes(
    reference: Route, degraded: Route, finish: tuple[float, float]
) -> RouteMetrics:
    """Compare a degraded route against the full-information reference."""
    if reference.eta_hours <= 0 or np.isnan(reference.eta_hours):
        raise ValueError("reference route has no ETA; cannot compute metrics")

    eta_ref = reference.eta_hours
    eta_deg = degraded.eta_hours if degraded.reached else float("nan")
    eta_diff = (
        (eta_deg - eta_ref) / eta_ref * 100.0 if degraded.reached else float("inf")
    )

    dist_diff = (
        (degraded.distance_nm - reference.distance_nm) / reference.distance_nm * 100.0
    )

    vmg_ref = mean_vmg(reference, finish)
    vmg_deg = mean_vmg(degraded, finish)
    vmg_diff = vmg_deg - vmg_ref

    bearing_ref = route_bearing(reference)
    bearing_deg = route_bearing(degraded)
    bearing_diff = float("nan")
    if not (np.isnan(bearing_ref) or np.isnan(bearing_deg)):
        diff = abs(bearing_deg - bearing_ref) % 360.0
        bearing_diff = float(min(diff, 360.0 - diff))

    return RouteMetrics(
        eta_diff_pct=eta_diff,
        distance_diff_pct=dist_diff,
        vmg_diff_kt=vmg_diff,
        max_wind_diff_kt=_max_wind(degraded) - _max_wind(reference),
        decision_divergence=(
            not np.isnan(bearing_diff) and bearing_diff > DECISION_SPLIT_DEG
        ),
        initial_bearing_diff_deg=bearing_diff,
        geographic_divergence_nm=_track_divergence(degraded, reference),
        reached=degraded.reached,
    )
