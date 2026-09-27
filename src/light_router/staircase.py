"""Budget staircase runner: the Goal 1 core experiment.

For each budget level, pick the highest-fidelity degradation configuration
that fits, re-route on the degraded weather, and measure route-quality
degradation against the Level 1 full-information reference route.

The harness speaks the canonical CF xarray Dataset (Compatibility rule 1)
and the Router protocol through a router factory (Compatibility rule 2):
``router_factory(weather_dataset) -> Router``. The in-repo isochrone and an
external oracle subprocess are interchangeable here.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

import xarray as xr

from .degrade import DegradeConfig, best_config_for_budget, degrade, package_size
from .dataset import grid_from_dataset, to_cf_dataset
from .isochrone import Route, Router
from .metrics import RouteMetrics, compare_routes
from .weather import WeatherGrid

RouterFactory = Callable[[xr.Dataset], Router]

STAIRCASE: list[int | None] = [
    None,  # unlimited
    1_000_000,  # 1 MB
    500_000,
    250_000,
    100_000,
    50_000,
    25_000,
    10_000,  # target operating point
    5_000,
    2_000,
    1_000,
]


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


def run_staircase(
    weather: xr.Dataset,
    router_factory: RouterFactory,
    start: tuple[float, float],
    finish: tuple[float, float],
    staircase: list[int | None] | None = None,
) -> StaircaseResult:
    """Run the degradation curve experiment. Returns one row per budget."""
    staircase = staircase if staircase is not None else STAIRCASE
    grid = grid_from_dataset(weather)
    reference = router_factory(weather).route(start, finish)
    if not reference.reached:
        raise RuntimeError(
            "reference route did not reach the finish; the scenario or the "
            "router horizon is mis-configured"
        )

    rows: list[StaircaseRow] = []
    for budget in staircase:
        config = best_config_for_budget(grid, budget)
        if config is None:
            continue  # budget unreachable even fully degraded
        rows.append(
            _run_level(grid, router_factory, reference, config, budget, start, finish)
        )
    return StaircaseResult(rows=rows, reference=reference)


def _run_level(
    grid: WeatherGrid,
    router_factory: RouterFactory,
    reference: Route,
    config: DegradeConfig,
    budget: int | None,
    start: tuple[float, float],
    finish: tuple[float, float],
) -> StaircaseRow:
    degraded_grid = degrade(grid, config)
    size = package_size(grid, config)
    route = router_factory(to_cf_dataset(degraded_grid)).route(start, finish)
    metrics = compare_routes(reference, route, finish)
    label = (
        "unlimited"
        if budget is None
        else f"{budget // 1000} KB"
        if budget >= 1000
        else f"{budget} B"
    )
    return StaircaseRow(
        budget=label,
        budget_bytes=budget,
        package_bytes=size,
        spatial_stride=config.spatial_stride,
        temporal_stride=config.temporal_stride,
        bits=config.bits,
        metrics=metrics,
        route=route,
    )


def format_summary(rows: list[StaircaseRow]) -> str:
    """Human-readable staircase table (the console summary)."""
    lines = [
        f"{'budget':>10} {'bytes':>9} {'s/t/b':>10} {'ETA diff':>9} "
        f"{'dist diff':>9} {'VMG diff':>8} {'decision':>8} {'geo div':>8}"
    ]
    for row in rows:
        m = row.metrics
        eta = f"{m.eta_diff_pct:+.1f}%" if m.reached else "n/a"
        lines.append(
            f"{row.budget:>10} {row.package_bytes:>9} "
            f"{row.spatial_stride}/{row.temporal_stride}/{row.bits:>2}   "
            f"{eta:>9} {m.distance_diff_pct:+7.1f}% {m.vmg_diff_kt:+7.2f} "
            f"{str(m.decision_divergence):>8} {m.geographic_divergence_nm:7.1f}nm"
        )
    return "\n".join(lines)


def write_csv(rows: list[StaircaseRow], path: Path) -> None:
    """Write the degradation curve as CSV."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(
            [
                "budget",
                "package_bytes",
                "spatial_stride",
                "temporal_stride",
                "bits",
                "reached",
                "eta_diff_pct",
                "distance_diff_pct",
                "vmg_diff_kt",
                "max_wind_diff_kt",
                "decision_divergence",
                "initial_bearing_diff_deg",
                "geographic_divergence_nm",
            ]
        )
        for row in rows:
            m = row.metrics
            writer.writerow(
                [
                    row.budget,
                    row.package_bytes,
                    row.spatial_stride,
                    row.temporal_stride,
                    row.bits,
                    m.reached,
                    f"{m.eta_diff_pct:.2f}",
                    f"{m.distance_diff_pct:.2f}",
                    f"{m.vmg_diff_kt:.3f}",
                    f"{m.max_wind_diff_kt:.2f}",
                    m.decision_divergence,
                    f"{m.initial_bearing_diff_deg:.1f}",
                    f"{m.geographic_divergence_nm:.1f}",
                ]
            )
