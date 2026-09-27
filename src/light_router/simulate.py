"""Operational passage simulation: the real-router mimic.

A real router at sea does not sail its forecast: it receives a new
(bandwidth-constrained) forecast package every cycle, replans from its
current position, and the boat actually advances on whatever the weather
really does. This module mimics that, virtually, for a past passage:

- the boat advances on **measured** weather (ERA5 reanalysis) — the truth
  grid, on the absolute passage clock;
- every ``cycle_hours`` (aligned with GFS run times: 00/06/12/18Z) the
  router receives the newest GFS run degraded to ``budget_bytes`` and
  replans from the boat's current position;
- the boat then follows the plan at the speed the *true* wind allows.

The whole passage is one experiment (one Gymnasium episode, Compatibility
rule 3): each planning cycle is a step, the degraded package is the
observation, the data request is the action, and the passage time versus
the unlimited-data reference is the reward.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import xarray as xr

from .dataset import grid_from_dataset, to_cf_dataset
from .degrade import DegradeConfig, best_config_for_budget, degrade, package_size
from .geo import destination, great_circle_distance, initial_bearing
from .isochrone import Route, RouterConfig
from .polar import PolarTable
from .scenario import surrogate_router_factory


@dataclass
class ForecastCycle:
    """One GFS run available to the router during the passage.

    init_hour: run initialization, in absolute hours since passage start.
    weather: the run's forecast as a CF Dataset, time = lead hours since
    its own initialization.
    """

    init_hour: float
    weather: xr.Dataset


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


def simulate_passage(
    truth: xr.Dataset,
    cycles: list[ForecastCycle],
    start: tuple[float, float],
    finish: tuple[float, float],
    polar: PolarTable,
    router_config: RouterConfig | None = None,
    *,
    budget_bytes: int | None = None,
    cycle_hours: float = 6.0,
    dt_hours: float = 1.0,
    finish_radius_nm: float = 25.0,
    max_hours: float = 240.0,
) -> PassageResult:
    """Simulate one passage: replan on degraded forecasts, sail on truth.

    ``truth`` is the measured-weather grid on the absolute passage clock
    (hours since passage start). ``cycles`` are the GFS runs the router
    may receive, sorted by init_hour; the newest run with
    ``init_hour <= t`` is used at each planning cycle.
    """
    if not cycles:
        raise ValueError("at least one forecast cycle is required")
    cycles = sorted(cycles, key=lambda c: c.init_hour)
    cfg = router_config if router_config is not None else RouterConfig()
    truth_grid = grid_from_dataset(truth)
    factory = surrogate_router_factory(polar, cfg)

    lat, lon = start
    t = 0.0
    cycle_idx = 0
    plan: Route | None = None
    plan_init = 0.0
    heading = float(initial_bearing(start[0], start[1], finish[0], finish[1]))
    track_lat: list[float] = [lat]
    track_lon: list[float] = [lon]
    track_time: list[float] = [0.0]
    track_heading: list[float] = []
    track_speed: list[float] = []
    track_tws: list[float] = []
    track_twa: list[float] = []
    records: list[CycleRecord] = []
    distance = 0.0

    while (
        great_circle_distance(lat, lon, finish[0], finish[1]) > finish_radius_nm
        and t < max_hours
    ):
        # planning cycle: consume every due forecast run, latest wins
        while cycle_idx < len(cycles) and cycles[cycle_idx].init_hour <= t:
            cycle = cycles[cycle_idx]
            grid = grid_from_dataset(cycle.weather)
            config = best_config_for_budget(grid, budget_bytes)
            if config is not None:
                size = package_size(grid, config)
                plan = factory(to_cf_dataset(degrade(grid, config))).route(
                    (lat, lon), finish, start_time=t - cycle.init_hour
                )
                plan_init = cycle.init_hour
                records.append(
                    CycleRecord(
                        hour=t,
                        config=config,
                        package_bytes=size,
                        plan_reached=plan.reached,
                        planned_arrival_hour=(
                            cycle.init_hour + plan.eta_hours if plan.reached else None
                        ),
                    )
                )
            else:
                # budget unreachable even fully degraded: no data this
                # cycle, the boat keeps following the previous plan
                records.append(
                    CycleRecord(
                        hour=t,
                        config=None,
                        package_bytes=0,
                        plan_reached=False,
                        planned_arrival_hour=None,
                    )
                )
            cycle_idx += 1

        # advance one dt along the plan, at the speed the true wind allows
        if plan is not None and plan.n_waypoints > 1:
            target = _plan_position_at(plan, t + dt_hours - plan_init)
            seg = great_circle_distance(lat, lon, target[0], target[1])
            if seg > 1e-9:
                heading = float(initial_bearing(lat, lon, target[0], target[1]))
        speed_arr, dir_arr = truth_grid.wind(
            np.asarray(t, dtype=float), np.asarray(lat, dtype=float), np.asarray(lon)
        )
        speed_kt, wind_from = float(speed_arr), float(dir_arr)
        twa = (heading - wind_from) % 360.0
        if twa > 180.0:
            twa = 360.0 - twa
        boat_speed = float(polar.boat_speed(speed_kt, twa))
        new_lat, new_lon = destination(lat, lon, heading, boat_speed * dt_hours)
        distance += float(great_circle_distance(lat, lon, new_lat, new_lon))
        lat, lon = float(new_lat), float(new_lon)
        t += dt_hours
        track_lat.append(lat)
        track_lon.append(lon)
        track_time.append(t)
        track_heading.append(heading)
        track_speed.append(boat_speed)
        track_tws.append(speed_kt)
        track_twa.append(twa)

    reached = bool(
        great_circle_distance(lat, lon, finish[0], finish[1]) <= finish_radius_nm
    )
    # waypoint 0 is the start (no leg yet): pad the per-leg arrays with NaN,
    # matching the Route convention.
    pad = np.array([np.nan])
    return PassageResult(
        lat=np.asarray(track_lat),
        lon=np.asarray(track_lon),
        time=np.asarray(track_time),
        heading=np.concatenate([pad, np.asarray(track_heading)]),
        speed=np.concatenate([pad, np.asarray(track_speed)]),
        tws=np.concatenate([pad, np.asarray(track_tws)]),
        twa=np.concatenate([pad, np.asarray(track_twa)]),
        reached=reached,
        passage_hours=t,
        distance_nm=distance,
        budget_bytes=budget_bytes,
        cycles=records,
    )


def run_operational_staircase(
    truth: xr.Dataset,
    cycles: list[ForecastCycle],
    start: tuple[float, float],
    finish: tuple[float, float],
    polar: PolarTable,
    budgets: list[int | None],
    router_config: RouterConfig | None = None,
    **sim_kwargs: object,
) -> list[PassageResult]:
    """Run the passage simulation once per budget (None = unlimited first)."""
    results: list[PassageResult] = []
    for budget in budgets:
        results.append(
            simulate_passage(
                truth,
                cycles,
                start,
                finish,
                polar,
                router_config,
                budget_bytes=budget,
                **sim_kwargs,  # type: ignore[arg-type]
            )
        )
    return results


def _plan_position_at(plan: Route, lead_time: float) -> tuple[float, float]:
    """Position on the planned track at a given lead time (clamped to ends)."""
    lat = float(np.interp(lead_time, plan.time, plan.lat))
    lon = float(np.interp(lead_time, plan.time, plan.lon))
    return lat, lon


def format_operational_summary(results: list[PassageResult]) -> str:
    """Human-readable operational table: budget vs actual passage."""
    reference = next((r for r in results if r.budget_bytes is None), results[0])
    lines = [
        f"{'budget':>10} {'pkg/cycle':>9} {'total KB':>9} {'cycles':>7} "
        f"{'passage h':>10} {'vs unlimited':>12} {'reached':>8}"
    ]
    for result in results:
        label = (
            "unlimited"
            if result.budget_bytes is None
            else f"{result.budget_bytes // 1000} KB"
            if result.budget_bytes >= 1000
            else f"{result.budget_bytes} B"
        )
        per_cycle = result.total_package_bytes // max(len(result.cycles), 1)
        total_kb = result.total_package_bytes / 1000
        diff = result.passage_hours - reference.passage_hours
        lines.append(
            f"{label:>10} {per_cycle:>9} {total_kb:>9.1f} "
            f"{len(result.cycles):>7} {result.passage_hours:>10.1f} "
            f"{diff:>+11.1f}h {str(result.reached):>8}"
        )
    return "\n".join(lines)
