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

from dataclasses import dataclass

import numpy as np
import xarray as xr

from light_router.dataset import grid_from_dataset, to_cf_dataset
from light_router.geo import destination, great_circle_distance, initial_bearing
from experiments.harness.degrade import best_config_for_budget, degrade, package_size
from experiments.harness.staircase import budget_label
from experiments.models.passage import CycleRecord, PassageResult
from light_router.models.forecast import ForecastCycle
from light_router.models.route import Route, RouterConfig
from light_router.models.vessel import PolarTable
from light_router.models.weather import WeatherGrid
from light_router.routing import RouterFactory
from experiments.simulation.scenario import surrogate_router_factory


@dataclass
class _PassageState:
    """Mutable state of one passage simulation: the boat, its plan and its
    recorded track. Held in one object so the step helpers stay small."""

    lat: float
    lon: float
    t: float
    heading: float
    plan: Route | None
    plan_init: float
    cycle_idx: int
    track_lat: list[float]
    track_lon: list[float]
    track_time: list[float]
    track_heading: list[float]
    track_speed: list[float]
    track_tws: list[float]
    track_twa: list[float]
    records: list[CycleRecord]
    distance: float


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

    state = _PassageState(
        lat=start[0],
        lon=start[1],
        t=0.0,
        heading=float(initial_bearing(start[0], start[1], finish[0], finish[1])),
        plan=None,
        plan_init=0.0,
        cycle_idx=0,
        track_lat=[start[0]],
        track_lon=[start[1]],
        track_time=[0.0],
        track_heading=[],
        track_speed=[],
        track_tws=[],
        track_twa=[],
        records=[],
        distance=0.0,
    )

    while (
        great_circle_distance(state.lat, state.lon, finish[0], finish[1])
        > finish_radius_nm
        and state.t < max_hours
    ):
        _replan_due_cycles(state, cycles, budget_bytes, factory, finish)
        _advance_step(state, truth_grid, polar, dt_hours)

    reached = bool(
        great_circle_distance(state.lat, state.lon, finish[0], finish[1])
        <= finish_radius_nm
    )
    # waypoint 0 is the start (no leg yet): pad the per-leg arrays with NaN,
    # matching the Route convention.
    pad = np.array([np.nan])
    return PassageResult(
        lat=np.asarray(state.track_lat),
        lon=np.asarray(state.track_lon),
        time=np.asarray(state.track_time),
        heading=np.concatenate([pad, np.asarray(state.track_heading)]),
        speed=np.concatenate([pad, np.asarray(state.track_speed)]),
        tws=np.concatenate([pad, np.asarray(state.track_tws)]),
        twa=np.concatenate([pad, np.asarray(state.track_twa)]),
        reached=reached,
        passage_hours=state.t,
        distance_nm=state.distance,
        budget_bytes=budget_bytes,
        cycles=state.records,
    )


def _replan_due_cycles(
    state: _PassageState,
    cycles: list[ForecastCycle],
    budget_bytes: int | None,
    factory: RouterFactory,
    finish: tuple[float, float],
) -> None:
    """Planning cycle: consume every due forecast run (latest wins), degrade
    the newest to the budget, and replan from the boat's current position."""
    while (
        state.cycle_idx < len(cycles) and cycles[state.cycle_idx].init_hour <= state.t
    ):
        cycle = cycles[state.cycle_idx]
        grid = grid_from_dataset(cycle.weather)
        config = best_config_for_budget(grid, budget_bytes)
        if config is not None:
            size = package_size(grid, config)
            state.plan = factory(to_cf_dataset(degrade(grid, config))).route(
                (state.lat, state.lon), finish, start_time=state.t - cycle.init_hour
            )
            state.plan_init = cycle.init_hour
            state.records.append(
                CycleRecord(
                    hour=state.t,
                    config=config,
                    package_bytes=size,
                    plan_reached=state.plan.reached,
                    planned_arrival_hour=(
                        cycle.init_hour + state.plan.eta_hours
                        if state.plan.reached
                        else None
                    ),
                )
            )
        else:
            # budget unreachable even fully degraded: no data this
            # cycle, the boat keeps following the previous plan
            state.records.append(
                CycleRecord(
                    hour=state.t,
                    config=None,
                    package_bytes=0,
                    plan_reached=False,
                    planned_arrival_hour=None,
                )
            )
        state.cycle_idx += 1


def _advance_step(
    state: _PassageState,
    truth_grid: WeatherGrid,
    polar: PolarTable,
    dt_hours: float,
) -> None:
    """Advance the boat one dt along the plan, at the speed the *true* wind
    allows, and append the track point."""
    if state.plan is not None and state.plan.n_waypoints > 1:
        target = _plan_position_at(state.plan, state.t + dt_hours - state.plan_init)
        seg = great_circle_distance(state.lat, state.lon, target[0], target[1])
        if seg > 1e-9:
            state.heading = float(
                initial_bearing(state.lat, state.lon, target[0], target[1])
            )
    speed_arr, dir_arr = truth_grid.wind(
        np.asarray(state.t, dtype=float),
        np.asarray(state.lat, dtype=float),
        np.asarray(state.lon),
    )
    speed_kt, wind_from = float(speed_arr), float(dir_arr)
    twa = (state.heading - wind_from) % 360.0
    if twa > 180.0:
        twa = 360.0 - twa
    boat_speed = float(polar.boat_speed(speed_kt, twa))
    new_lat, new_lon = destination(
        state.lat, state.lon, state.heading, boat_speed * dt_hours
    )
    state.distance += float(
        great_circle_distance(state.lat, state.lon, new_lat, new_lon)
    )
    state.lat, state.lon = float(new_lat), float(new_lon)
    state.t += dt_hours
    state.track_lat.append(state.lat)
    state.track_lon.append(state.lon)
    state.track_time.append(state.t)
    state.track_heading.append(state.heading)
    state.track_speed.append(boat_speed)
    state.track_tws.append(speed_kt)
    state.track_twa.append(twa)


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
        label = budget_label(result.budget_bytes)
        per_cycle = result.total_package_bytes // max(len(result.cycles), 1)
        total_kb = result.total_package_bytes / 1000
        diff = result.passage_hours - reference.passage_hours
        lines.append(
            f"{label:>10} {per_cycle:>9} {total_kb:>9.1f} "
            f"{len(result.cycles):>7} {result.passage_hours:>10.1f} "
            f"{diff:>+11.1f}h {str(result.reached):>8}"
        )
    return "\n".join(lines)
