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
    """What the router received, decided and believed at one planning cycle."""

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

    cumulative_bytes: int = 0
    """Running ledger: total package bytes this budget's router has received
    by this cycle (issue #14) — the curve a data plan is priced against."""

    planned_bearing_deg: float | None = None
    """Initial bearing of the new plan (deg true) — the immediate helm
    decision (issue #15); None when no data arrived this cycle."""

    plan_checksum: str | None = None
    """Short SHA-256 digest of the planned track (issue #15) — plan identity
    per cycle without the weight of a GPX per cycle."""

    churn_nm: float | None = None
    """Plan-to-plan divergence (nm): mean distance between this plan and the
    previous one over their overlapping window (issue #15) — the operational
    cost of fresh data. None on the first plan."""

    execution_error_nm: float | None = None
    """Plan-vs-actual divergence (nm): how far the boat is at this cycle from
    where the previous plan predicted it would be (issue #15). None on the
    first plan."""

    belief_error_h: float | None = None
    """Belief error (h): the arrival this cycle believed minus the actual
    arrival (issue #15). Filled after the passage ends; None when the plan
    did not reach or the boat never arrived."""

    forecast_error_kt: float | None = None
    """Wind-speed error (kt) between the degraded forecast the router
    believed and the truth, at the boat's position at cycle time
    (issue #17) — the error replanning absorbs and adaptive acquisition
    will act on."""

    forecast_staleness_h: float | None = None
    """Age of the newest forecast run when consumed (h) — init lag
    (issue #17)."""

    compute_seconds: float | None = None
    """Wall-clock time of this cycle's replan (s) — onboard feasibility
    (issue #19). The one non-deterministic artifact field: record it, but
    exclude it from any artifact-equality check (Decision #18)."""


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

    @property
    def max_tws_kt(self) -> float:
        """Maximum true wind experienced along the track (kt) — the safety
        half of the degradation review (issue #18): a budget must not buy
        ETA by sailing through worse weather."""
        return float(np.nanmax(self.tws))

    @property
    def mean_tws_kt(self) -> float:
        """Mean true wind experienced along the track (kt) (issue #18)."""
        return float(np.nanmean(self.tws))

    @property
    def upwind_fraction(self) -> float:
        """Fraction of track points sailed upwind (TWA <= 60 deg)
        (issue #18)."""
        twa = self.twa[~np.isnan(self.twa)]
        return float(np.mean(twa <= 60.0)) if len(twa) else 0.0

    @property
    def downwind_fraction(self) -> float:
        """Fraction of track points sailed downwind (TWA >= 120 deg)
        (issue #18)."""
        twa = self.twa[~np.isnan(self.twa)]
        return float(np.mean(twa >= 120.0)) if len(twa) else 0.0

    @property
    def compute_seconds_total(self) -> float:
        """Total replan wall-clock time over the passage (s) (issue #19)."""
        return float(sum(r.compute_seconds or 0.0 for r in self.cycles))

    @property
    def compute_seconds_mean(self) -> float:
        """Mean replan wall-clock time per data cycle (s) (issue #19)."""
        times = [
            r.compute_seconds for r in self.cycles if r.compute_seconds is not None
        ]
        return float(np.mean(times)) if times else 0.0

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
        )
