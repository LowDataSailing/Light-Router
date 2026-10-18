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

import hashlib
import time
from dataclasses import dataclass

import numpy as np
import xarray as xr

from light_router.dataset import grid_from_dataset, to_cf_dataset
from light_router.geo import destination, great_circle_distance, initial_bearing
from experiments.harness.degrade import (
    CompressionMethod,
    budget_staircase_compression,
)
from experiments.harness.staircase import budget_label
from experiments.models.passage import CycleRecord, PassageResult
from light_router.models.forecast import ForecastCycle
from light_router.models.route import Route, route_bearing
from light_router.models.vessel import PolarTable
from light_router.models.weather import WeatherGrid
from light_router.routing import Router


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
    ledger_bytes: int
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
    router: Router,
    polar: PolarTable,
    compression: CompressionMethod = budget_staircase_compression,
    *,
    budget_bytes: int | None = None,
    dt_hours: float = 1.0,
    finish_radius_nm: float = 25.0,
    max_hours: float = 240.0,
) -> PassageResult:
    """Simulate one passage: replan on degraded forecasts, sail on truth.

    A real router at sea does not sail its forecast: it receives a new
    (bandwidth-constrained) forecast package whenever a run becomes due,
    replans from its current position, and the boat advances on whatever
    the weather really does. This function mimics that, virtually, for a
    past passage.

    Args:
        truth: The measured-weather grid on the absolute passage clock
            (hours since passage start): the boat advances on it whatever
            the forecast said. The source behind it is the experiment's
            choice — the simulation is source-agnostic.
        cycles: The forecast runs the router may receive, sorted by
            ``init_hour``; at each planning opportunity the newest run
            with ``init_hour <= t`` is degraded to the budget and
            consumed. The replan cadence is therefore a property of this
            data (today: one run every 6 h), not a knob.
        start: Passage start, ``(lat, lon)`` in degrees.
        finish: Passage finish, ``(lat, lon)`` in degrees.
        router: One router setup (its config travels in its attributes);
            re-bound to every received package via ``for_weather``.
        polar: The boat's speed model — the boat advances on the truth
            wind at the speed the polar allows.
        compression: The degradation seam — how a forecast run becomes a
            bandwidth-constrained package. Must report *measured* bytes;
            ``None`` return means the budget cannot be met (no data this
            cycle). Adaptive acquisition plugs in here.
        budget_bytes: Cap on each received package; ``None`` means
            unlimited — the reference condition of the staircase.
        dt_hours: Simulation step: the boat advances in steps of this
            size along the current plan, at the speed the *true* wind
            allows.
        finish_radius_nm: Arrival radius around the finish; the passage
            ends (``reached`` is True) once the boat enters it.
        max_hours: Simulation horizon: a passage that cannot finish
            within it ends partial (``reached`` is False).

    Returns:
        The passage as it actually happened: track, arrival, and the
        per-cycle records of what was received and believed.
    """
    if not cycles:
        raise ValueError("at least one forecast cycle is required")
    cycles = sorted(cycles, key=lambda c: c.init_hour)
    truth_grid = grid_from_dataset(truth)

    state = _PassageState(
        lat=start[0],
        lon=start[1],
        t=0.0,
        heading=float(initial_bearing(start[0], start[1], finish[0], finish[1])),
        plan=None,
        plan_init=0.0,
        cycle_idx=0,
        ledger_bytes=0,
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
        _replan_due_cycles(
            state, cycles, budget_bytes, router, compression, finish, truth_grid
        )
        _advance_step(state, truth_grid, polar, dt_hours)

    reached = bool(
        great_circle_distance(state.lat, state.lon, finish[0], finish[1])
        <= finish_radius_nm
    )
    # belief error (issue #15): what each cycle believed about arrival vs the
    # actual arrival — nearly free, both sides already exist.
    if reached:
        for record in state.records:
            if record.planned_arrival_hour is not None:
                record.belief_error_h = record.planned_arrival_hour - state.t
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
    router: Router,
    compression: CompressionMethod,
    finish: tuple[float, float],
    truth_grid: WeatherGrid,
) -> None:
    """Planning cycle: consume every due forecast run (latest wins), compress
    the newest to the budget, and replan from the boat's current position.

    Records the decision log (issue #15), the forecast error and staleness
    (issue #17), the bandwidth ledger (issue #14) and the replan compute
    time (issue #19) on each :class:`CycleRecord`.
    """
    while (
        state.cycle_idx < len(cycles) and cycles[state.cycle_idx].init_hour <= state.t
    ):
        cycle = cycles[state.cycle_idx]
        grid = grid_from_dataset(cycle.weather)
        package = compression(grid, budget_bytes)
        record = CycleRecord(
            hour=state.t,
            config=package.config if package is not None else None,
            package_bytes=package.package_bytes if package is not None else 0,
            plan_reached=False,
            planned_arrival_hour=None,
        )
        if package is not None:
            started = time.perf_counter()
            plan = router.for_weather(to_cf_dataset(package.grid)).route(
                (state.lat, state.lon), finish, start_time=state.t - cycle.init_hour
            )
            record.compute_seconds = time.perf_counter() - started

            # decision log (issue #15): what the router decided, not just
            # received — bearing, plan identity, churn, execution error.
            record.planned_bearing_deg = (
                route_bearing(plan) if plan.n_waypoints > 1 else None
            )
            record.plan_checksum = _plan_checksum(plan)
            if state.plan is not None:
                record.churn_nm = _plan_divergence_nm(
                    state.plan, state.plan_init, plan, cycle.init_hour
                )
                pred_lat, pred_lon = _plan_position_at(
                    state.plan, state.t - state.plan_init
                )
                record.execution_error_nm = float(
                    great_circle_distance(state.lat, state.lon, pred_lat, pred_lon)
                )

            # forecast-vs-truth error at the boat (issue #17): what the
            # router believed (degraded forecast) against what is true.
            fc_speed, _ = package.grid.wind(
                np.asarray(state.t - cycle.init_hour),
                np.asarray(state.lat),
                np.asarray(state.lon),
            )
            truth_speed, _ = truth_grid.wind(
                np.asarray(state.t),
                np.asarray(state.lat),
                np.asarray(state.lon),
            )
            record.forecast_error_kt = abs(float(fc_speed) - float(truth_speed))
            record.forecast_staleness_h = state.t - cycle.init_hour

            record.plan_reached = plan.reached
            record.planned_arrival_hour = (
                cycle.init_hour + plan.eta_hours if plan.reached else None
            )
            state.plan = plan
            state.plan_init = cycle.init_hour
        # budget unreachable even fully degraded: no data this cycle, the
        # boat keeps following the previous plan (record already says so)
        # bandwidth ledger (issue #14): cumulative delivered bytes by cycle.
        state.ledger_bytes += record.package_bytes
        record.cumulative_bytes = state.ledger_bytes
        state.records.append(record)
        state.cycle_idx += 1


def _plan_checksum(plan: Route) -> str:
    """Short SHA-256 over the planned track — plan identity (issue #15)."""
    h = hashlib.sha256()
    for arr in (plan.lat, plan.lon, plan.time):
        h.update(np.ascontiguousarray(arr, dtype=float).tobytes())
    return h.hexdigest()[:16]


def _plan_divergence_nm(
    prev: Route, prev_init: float, new: Route, new_init: float
) -> float | None:
    """Mean distance (nm) between two plans over their overlapping absolute
    time window — plan-to-plan churn (issue #15).

    Plan time axes are lead hours since their own run's initialization;
    absolute time = lead + init. Returns None when the plans do not overlap.
    """
    t0 = max(float(new.time[0]) + new_init, float(prev.time[0]) + prev_init)
    t1 = min(float(new.time[-1]) + new_init, float(prev.time[-1]) + prev_init)
    if t1 <= t0:
        return None
    samples = np.linspace(t0, t1, 32)
    prev_lat = np.interp(samples - prev_init, prev.time, prev.lat)
    prev_lon = np.interp(samples - prev_init, prev.time, prev.lon)
    new_lat = np.interp(samples - new_init, new.time, new.lat)
    new_lon = np.interp(samples - new_init, new.time, new.lon)
    return float(np.mean(great_circle_distance(prev_lat, prev_lon, new_lat, new_lon)))


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
    router: Router,
    polar: PolarTable,
    budgets: list[int | None],
    compression: CompressionMethod = budget_staircase_compression,
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
                router,
                polar,
                compression,
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


def format_operational_summary(
    results: list[PassageResult], price_per_kb: float | None = None
) -> str:
    """Human-readable operational table: budget vs actual passage.

    ``price_per_kb`` (EUR/KB, issue #14) adds the bandwidth-price column —
    the cost of each passage's delivered bytes (Decision #21: delivered
    package bytes only).
    """
    reference = next((r for r in results if r.budget_bytes is None), results[0])
    cost_head = f"{'cost EUR':>9} " if price_per_kb is not None else ""
    lines = [
        f"{'budget':>10} {'pkg/cycle':>9} {'total KB':>9} {cost_head}"
        f"{'cycles':>7} {'passage h':>10} {'vs unlimited':>12} "
        f"{'max wind kt':>11} {'compute s':>9} {'reached':>8}"
    ]
    for result in results:
        label = budget_label(result.budget_bytes)
        per_cycle = result.total_package_bytes // max(len(result.cycles), 1)
        total_kb = result.total_package_bytes / 1000
        diff = result.passage_hours - reference.passage_hours
        cost_cell = (
            f"{total_kb * price_per_kb:>9.2f} " if price_per_kb is not None else ""
        )
        lines.append(
            f"{label:>10} {per_cycle:>9} {total_kb:>9.1f} {cost_cell}"
            f"{len(result.cycles):>7} {result.passage_hours:>10.1f} "
            f"{diff:>+11.1f}h {result.max_tws_kt:>11.1f} "
            f"{result.compute_seconds_mean:>9.2f} {str(result.reached):>8}"
        )
    return "\n".join(lines)
