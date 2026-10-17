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
    """What the router received and planned at one planning cycle.

    hour: absolute cycle time (h since passage start). config: the
    degradation config received, or None when the budget was unreachable
    even fully degraded (no data this cycle). package_bytes: the size of
    the received package. plan_reached: whether the replanned route
    reached the finish within the forecast horizon. planned_arrival_hour:
    the believed arrival (absolute h) at cycle time, None if not reached.
    """

    hour: float
    config: DegradeConfig | None
    package_bytes: int
    plan_reached: bool
    planned_arrival_hour: float | None


@dataclass
class PassageResult:
    """The actual passage as it happened on the measured weather.

    lat/lon/time: the track (deg, absolute h since passage start).
    heading: deg true; speed: kt achieved on the true wind; tws/twa: the
    true wind speed (kt) and angle (deg) experienced. reached: whether
    the finish radius was entered; passage_hours/distance_nm: the
    outcome; budget_bytes: the per-cycle budget this passage ran under;
    cycles: the per-cycle records.
    """

    lat: np.ndarray
    lon: np.ndarray
    time: np.ndarray
    heading: np.ndarray
    speed: np.ndarray
    tws: np.ndarray
    twa: np.ndarray
    reached: bool
    passage_hours: float
    distance_nm: float
    budget_bytes: int | None
    cycles: list[CycleRecord] = field(repr=False, compare=False)

    @property
    def total_package_bytes(self) -> int:
        return sum(record.package_bytes for record in self.cycles)

    def as_route(self) -> Route:
        """The actual track as a Route, for export (GPX/GeoJSON) and plots."""
        return Route(
            lat=self.lat,
            lon=self.lon,
            time=self.time,
            heading=self.heading,
            speed=self.speed,
            tws=self.tws,
            twa=self.twa,
            reached=self.reached,
            eta_hours=self.passage_hours if self.reached else float("nan"),
            distance_nm=self.distance_nm,
        )
