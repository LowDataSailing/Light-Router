"""Operational simulation: replan on degraded forecasts, sail on truth."""

from __future__ import annotations

import numpy as np
import pytest

from light_router.dataset import to_cf_dataset
from light_router.routing import RouterConfig
from light_router.models.vessel import synthetic_cruising_polar
from light_router.simulation.simulate import (
    ForecastCycle,
    format_operational_summary,
    run_operational_staircase,
    simulate_passage,
)
from light_router.synthetic import trade_wind_field

START = (29.5, -13.5)
FINISH = (26.5, -16.5)

ROUTER_CONFIG = RouterConfig(
    dt_hours=2.0,
    n_headings=18,
    bin_deg=1.0,
    max_points=300,
    finish_radius_nm=15.0,
    max_hours=60.0,
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
        synthetic_cruising_polar(),
        ROUTER_CONFIG,
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
        synthetic_cruising_polar(),
        ROUTER_CONFIG,
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
        synthetic_cruising_polar(),
        ROUTER_CONFIG,
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
        synthetic_cruising_polar(),
        ROUTER_CONFIG,
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
        synthetic_cruising_polar(),
        [None, 3000],
        ROUTER_CONFIG,
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
            synthetic_cruising_polar(),
            ROUTER_CONFIG,
        )
