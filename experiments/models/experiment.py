"""Experiment records: the output of one staircase run.

``RouteMetrics`` is the degradation measurement (reported separately, never
combined into one score); ``StaircaseRow`` / ``StaircaseResult`` are the
staircase's per-budget and overall outputs. The harness produces them;
reporting consumes them.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field

from light_router.models.route import Route


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
        """Metrics as a flat dict (one CSV/JSON row)."""
        return asdict(self)


@dataclass
class StaircaseRow:
    budget: str
    budget_bytes: int | None
    package_bytes: int
    spatial_stride: int
    temporal_stride: int
    bits: int
    metrics: RouteMetrics
    route: Route = field(repr=False, compare=False)


@dataclass
class StaircaseResult:
    """Staircase output: one row per budget plus the Level 1 reference route."""

    rows: list[StaircaseRow]
    reference: Route
