"""Operational simulation: replan on degraded forecasts, sail on truth."""

from __future__ import annotations

import numpy as np
import pytest

from light_router.dataset import to_cf_dataset
from light_router.routing import IsochroneRouter
from experiments.synthetic_polar import synthetic_cruising_polar
from experiments.simulation.simulate import (
    ForecastCycle,
    format_operational_summary,
    run_operational_staircase,
    simulate_passage,
)
from experiments.synthetic import trade_wind_field

START = (29.5, -13.5)
FINISH = (26.5, -16.5)

ROUTER_KWARGS = dict(
    dt_hours=2.0,
    n_headings=18,
    bin_deg=1.0,
    max_points=300,
    finish_radius_nm=15.0,
    max_hours=60.0,
)


def make_router(weather):
    """One router setup; the simulation re-binds it to every package."""
    return IsochroneRouter.from_dataset(
        weather, synthetic_cruising_polar(), **ROUTER_KWARGS
    )


def make_weather(wind_kt: float = 15.0, direction_from_deg: float = 45.0):
    lats = np.arange(25.5, 30.51, 0.5)
    lons = np.arange(-17.5, -12.99, 0.5)
    times = np.arange(0.0, 49.0, 6.0)
    return to_cf_dataset(
        trade_wind_field(
            lats,
            lons,
            times,
            mean_speed_kt=wind_kt,
            direction_from_deg=direction_from_deg,
        )
    )


def make_cycles(weather, init_hours=(0.0, 6.0, 12.0, 18.0, 24.0)):
    return [ForecastCycle(init_hour=h, weather=weather) for h in init_hours]


def test_perfect_forecast_reaches():
    weather = make_weather()
    result = simulate_passage(
        weather,
        make_cycles(weather),
        START,
        FINISH,
        make_router(weather),
        synthetic_cruising_polar(),
        max_hours=60.0,
    )
    assert result.reached
    assert result.passage_hours < 60.0
    assert result.distance_nm > 100.0


def test_replans_at_cycle_boundaries():
    weather = make_weather()
    result = simulate_passage(
        weather,
        make_cycles(weather),
        START,
        FINISH,
        make_router(weather),
        synthetic_cruising_polar(),
        max_hours=60.0,
    )
    hours = [record.hour for record in result.cycles]
    assert hours[0] == 0.0
    # cycles are consumed in order, every 6 h, until arrival
    assert hours == sorted(hours)
    assert all(h2 - h1 == 6.0 for h1, h2 in zip(hours, hours[1:]))
    assert all(record.config is not None for record in result.cycles)
    assert all(record.package_bytes > 0 for record in result.cycles)
    # with a perfect forecast the plan always believes it will arrive
    assert all(record.plan_reached for record in result.cycles)


def test_budget_caps_each_package():
    weather = make_weather()
    result = simulate_passage(
        weather,
        make_cycles(weather),
        START,
        FINISH,
        make_router(weather),
        synthetic_cruising_polar(),
        budget_bytes=3000,
        max_hours=60.0,
    )
    assert all(record.package_bytes <= 3000 for record in result.cycles)


def test_boat_sails_on_truth_not_forecast():
    """The boat advances on measured weather, not on the forecast.

    Forecast promises 15 kt trades; the measured weather is calm — the
    boat must not move, whatever the router believes.
    """
    forecast = make_weather(wind_kt=15.0)
    calm = make_weather(wind_kt=0.05)
    result = simulate_passage(
        calm,
        make_cycles(forecast),
        START,
        FINISH,
        make_router(forecast),
        synthetic_cruising_polar(),
        max_hours=24.0,
    )
    assert not result.reached
    assert result.distance_nm < 5.0
    # the router still planned confidently on its (wrong) forecast
    assert all(record.plan_reached for record in result.cycles)


def test_staircase_runs_each_budget():
    weather = make_weather()
    results = run_operational_staircase(
        weather,
        make_cycles(weather),
        START,
        FINISH,
        make_router(weather),
        synthetic_cruising_polar(),
        [None, 3000],
        max_hours=60.0,
    )
    assert [r.budget_bytes for r in results] == [None, 3000]
    assert all(r.reached for r in results)
    summary = format_operational_summary(results)
    assert "unlimited" in summary
    assert "passage h" in summary


def test_no_cycles_raises():
    weather = make_weather()
    with pytest.raises(ValueError, match="forecast cycle"):
        simulate_passage(
            weather,
            [],
            START,
            FINISH,
            make_router(weather),
            synthetic_cruising_polar(),
        )


# --- ledger, decision log, monitoring ------------


def run_passage(wind_kt=15.0, truth_wind_kt=None, **kwargs):
    weather = make_weather(wind_kt=wind_kt)
    truth = make_weather(wind_kt=truth_wind_kt) if truth_wind_kt else weather
    kwargs.setdefault("max_hours", 60.0)
    return simulate_passage(
        truth,
        make_cycles(weather),
        START,
        FINISH,
        make_router(weather),
        synthetic_cruising_polar(),
        **kwargs,
    )


def test_cycle_records_carry_the_decision_log():
    result = run_passage()
    records = result.cycles
    assert len(records) >= 2
    first, later = records[0], records[1]
    # helm decision + plan identity
    assert first.planned_bearing_deg is not None
    assert 0.0 <= first.planned_bearing_deg < 360.0
    assert len(first.plan_checksum) == 16
    # first plan has no churn / execution error; later plans do
    assert first.churn_nm is None and first.execution_error_nm is None
    assert later.churn_nm is not None and later.churn_nm >= 0.0
    assert later.execution_error_nm is not None and later.execution_error_nm >= 0.0
    # belief error: filled for reached plans, small on a
    # perfect forecast
    assert all(r.belief_error_h is not None for r in records)
    assert all(abs(r.belief_error_h) < 10.0 for r in records)
    # forecast error: recorded every data cycle. On this
    # fixture each cycle replays the passage-start field, so the error is
    # the temporal modulation gap — small but nonzero, and staleness is 0
    # (runs are consumed exactly at their init time).
    assert all(r.forecast_error_kt is not None for r in records)
    assert all(0.0 <= r.forecast_error_kt < 5.0 for r in records)
    assert all(r.forecast_staleness_h == 0.0 for r in records)
    # compute time recorded, non-negative
    assert all(
        r.compute_seconds is not None and r.compute_seconds >= 0.0 for r in records
    )


def test_bandwidth_ledger_accumulates():
    result = run_passage(budget_bytes=3000)
    cumulative = [r.cumulative_bytes for r in result.cycles]
    assert cumulative == sorted(cumulative)
    assert cumulative[-1] == result.total_package_bytes
    assert all(r.package_bytes <= 3000 for r in result.cycles)


def test_forecast_error_exposed_on_a_bad_forecast():
    # the router believes 15 kt trades; the truth is calm
    result = run_passage(wind_kt=15.0, truth_wind_kt=0.05, max_hours=24.0)
    assert all(r.forecast_error_kt > 10.0 for r in result.cycles)


def test_experienced_weather_properties():
    result = run_passage()
    assert 10.0 <= result.max_tws_kt <= 20.0  # 15 kt trades +- 15%
    assert 10.0 <= result.mean_tws_kt <= 20.0
    assert 0.0 <= result.upwind_fraction <= 1.0
    assert 0.0 <= result.downwind_fraction <= 1.0
    assert result.upwind_fraction + result.downwind_fraction <= 1.0
    assert result.compute_seconds_total >= 0.0
    assert result.compute_seconds_mean >= 0.0


def test_summary_reports_cost_and_weather():
    weather = make_weather()
    results = run_operational_staircase(
        weather,
        make_cycles(weather),
        START,
        FINISH,
        make_router(weather),
        synthetic_cruising_polar(),
        [None, 3000],
        max_hours=60.0,
    )
    summary = format_operational_summary(results, price_per_kb=0.01)
    assert "cost EUR" in summary
    assert "max wind kt" in summary
    assert "compute s" in summary
    plain = format_operational_summary(results)
    assert "cost EUR" not in plain
