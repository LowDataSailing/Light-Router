"""Compatibility rules 2 and 3: Scenario + Router factory + Gymnasium semantics."""

from __future__ import annotations

import numpy as np

from light_router.dataset import to_cf_dataset
from light_router.isochrone import Router, RouterConfig
from light_router.polar import synthetic_cruising_polar
from light_router.scenario import Scenario, surrogate_router_factory
from light_router.staircase import STAIRCASE
from light_router.synthetic import trade_wind_field

START = (28.0, -15.5)
FINISH = (16.75, -22.9)


def make_weather():
    lats = np.arange(12.0, 32.01, 1.0)
    lons = np.arange(-26.0, -12.99, 1.0)
    times = np.arange(0.0, 121.0, 6.0)
    return to_cf_dataset(
        trade_wind_field(lats, lons, times, mean_speed_kt=15.0, direction_from_deg=45.0)
    )


def test_surrogate_factory_returns_router():
    weather = make_weather()
    factory = surrogate_router_factory(synthetic_cruising_polar())
    router = factory(weather)
    assert isinstance(router, Router)  # runtime_checkable protocol


def test_scenario_runs_staircase():
    scenario = Scenario(weather=make_weather(), start=START, finish=FINISH)
    factory = surrogate_router_factory(
        synthetic_cruising_polar(),
        RouterConfig(
            dt_hours=4.0,
            n_headings=18,
            bin_deg=2.0,
            max_points=400,
            finish_radius_nm=40.0,
            max_hours=250.0,
        ),
    )
    result = scenario.run(factory)
    assert result.reference.reached
    assert [row.budget_bytes for row in result.rows] == [budget for budget in STAIRCASE]


def test_scenario_custom_staircase():
    scenario = Scenario(
        weather=make_weather(),
        start=START,
        finish=FINISH,
        staircase=[None, 10_000],
    )
    factory = surrogate_router_factory(
        synthetic_cruising_polar(),
        RouterConfig(
            dt_hours=4.0,
            n_headings=18,
            bin_deg=2.0,
            max_points=400,
            finish_radius_nm=40.0,
            max_hours=250.0,
        ),
    )
    result = scenario.run(factory)
    assert len(result.rows) == 2
    assert result.rows[0].budget == "unlimited"


def test_scenario_start_time_default():
    scenario = Scenario(weather=make_weather(), start=START, finish=FINISH)
    assert scenario.start_time == 0.0
    assert scenario.staircase == list(STAIRCASE)
