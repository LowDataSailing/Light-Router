"""Passage records: what the router received and what actually happened.

``CycleRecord`` is what the router received and believed at one planning
cycle; ``PassageResult`` is the passage as it actually happened on the
measured weather. (The forecast runs themselves are weather-domain:
``light_router.models.forecast.ForecastCycle``.)
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from experiments.models.degradation import DegradeConfig
from light_router.models.route import Route


@dataclass
class CycleRecord:
    """What the router received and planned at one planning cycle."""

    hour: float
    """Absolute cycle time (h since passage start)."""

    config: DegradeConfig | None
    """The degradation config received; None when the budget was
    unreachable even fully degraded (no data this cycle)."""

    package_bytes: int
    """Size of the received package (bytes)."""

    plan_reached: bool
    """Whether the replanned route reached the finish within the forecast
    horizon."""

    planned_arrival_hour: float | None
    """The believed arrival (absolute h) at cycle time; None if not
    reached."""


@dataclass
class PassageResult:
    """The actual passage as it happened on the measured weather."""

    lat: np.ndarray
    """Track latitudes (deg)."""

    lon: np.ndarray
    """Track longitudes (deg)."""

    time: np.ndarray
    """Absolute hours since passage start, one per track point."""

    heading: np.ndarray
    """Heading per track point (deg true); NaN at the start point."""

    speed: np.ndarray
    """Boat speed per track point (kt), achieved on the true wind."""

    tws: np.ndarray
    """True wind speed experienced per track point (kt)."""

    twa: np.ndarray
    """True wind angle experienced per track point (deg)."""

    reached: bool
    """Whether the finish radius was entered."""

    passage_hours: float
    """Total passage time (h since passage start)."""

    distance_nm: float
    """Total distance sailed (nm)."""

    budget_bytes: int | None
    """The per-cycle budget this passage ran under (None = unlimited)."""

    cycles: list[CycleRecord] = field(repr=False, compare=False)
    """The per-cycle records of what was received and believed."""

    @property
    def total_package_bytes(self) -> int:
        return sum(record.package_bytes for record in self.cycles)

    def as_route(self) -> Route:
        """The actual track as a Route, for export (GPX/GeoJSON) and plots.

        The route carries the track geometry only; the experienced weather
        stays on the passage result (it is simulation output, not router
        output) and is sampled where exports need it.
        """
        from light_router.models.route import Waypoint

        return Route(
            waypoints=[
                Waypoint(lat=float(la), lon=float(lo), time=float(ti))
                for la, lo, ti in zip(self.lat, self.lon, self.time)
            ],
            reached=self.reached,
            eta_hours=self.passage_hours if self.reached else float("nan"),
            distance_nm=self.distance_nm,
        )
