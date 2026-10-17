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

    hour: float  # absolute cycle time
    config: DegradeConfig | None  # None = budget unreachable even fully degraded
    package_bytes: int
    plan_reached: bool
    planned_arrival_hour: float | None  # absolute, as believed at cycle time


@dataclass
class PassageResult:
    """The actual passage as it happened on the measured weather."""

    lat: np.ndarray
    lon: np.ndarray
    time: np.ndarray  # absolute hours since passage start
    heading: np.ndarray
    speed: np.ndarray  # kt achieved on the true wind
    tws: np.ndarray  # true wind speed experienced (kt)
    twa: np.ndarray  # true wind angle experienced (deg)
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
