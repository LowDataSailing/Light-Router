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
    """Degradation of one route vs the reference route, one axis per field.

    Reported separately, never combined into a single score.
    """

    eta_diff_pct: float
    """Arrival-time difference, percent of the reference ETA."""

    distance_diff_pct: float
    """Sailed-distance difference, percent of the reference distance."""

    vmg_diff_kt: float
    """Difference in velocity-made-good toward the finish (kt)."""

    max_wind_diff_kt: float
    """Difference in the maximum wind encountered (kt)."""

    decision_divergence: bool
    """Whether the first tactical decision differs from the reference."""

    initial_bearing_diff_deg: float
    """Difference in the initial bearing (deg)."""

    geographic_divergence_nm: float
    """Mean nearest-track distance (nm); both tracks resampled to 50
    equal-progress points."""

    reached: bool
    """Whether the degraded route reached the finish."""

    def as_dict(self) -> dict[str, object]:
        """Metrics as a flat dict (one CSV/JSON row)."""
        return asdict(self)


@dataclass
class StaircaseRow:
    """One staircase level: budget, chosen config, measured size, metrics."""

    budget: str
    """Display label ("unlimited", "10 KB")."""

    budget_bytes: int | None
    """The budget in bytes (None = unlimited)."""

    package_bytes: int
    """Measured size of the degraded package (bytes)."""

    spatial_stride: int
    """Spatial stride of the chosen config."""

    temporal_stride: int
    """Temporal stride of the chosen config."""

    bits: int
    """Quantization depth of the chosen config."""

    metrics: RouteMetrics
    """Degradation of this level's route vs the reference."""

    route: Route = field(repr=False, compare=False)
    """The computed route for this level."""


@dataclass
class StaircaseResult:
    """Staircase output: one row per budget plus the Level 1 reference route."""

    rows: list[StaircaseRow]
    reference: Route
