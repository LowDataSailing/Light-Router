"""libweatherrouting oracle adapter: live cross-check (optional oracle group)."""

from __future__ import annotations

import numpy as np
import pytest

from light_router.dataset import to_cf_dataset
from light_router.routing import Router
from experiments.oracle.libweatherrouting import (
    LibWeatherRoutingConfig,
    LibWeatherRoutingRouter,
)
from experiments.synthetic import trade_wind_field
from experiments.synthetic_polar import synthetic_cruising_polar

weatherrouting = pytest.importorskip(
    "weatherrouting", reason="optional 'oracle' dependency group not installed"
)

START = (28.0, -15.5)
FINISH = (26.0, -15.9)  # ~2 deg south: a short, fast passage for tests


def make_weather():
    lats = np.arange(24.0, 30.01, 0.5)
    lons = np.arange(-18.0, -13.99, 0.5)
    times = np.arange(0.0, 49.0, 6.0)
    return to_cf_dataset(trade_wind_field(lats, lons, times))


def make_router() -> LibWeatherRoutingRouter:
    return LibWeatherRoutingRouter(
        weather=make_weather(),
        polar=synthetic_cruising_polar(),
        config=LibWeatherRoutingConfig(dt_hours=1.0, subdiv=5, max_hours=48.0),
    )


def test_satisfies_router_protocol():
    assert isinstance(make_router(), Router)


def test_name_carries_measured_version():
    assert make_router().name.startswith("libweatherrouting@")
    assert weatherrouting.__name__ == "weatherrouting"


def test_route_reaches_finish():
    from light_router.dataset import grid_from_dataset
    from light_router.sampling import wind_along_route

    router = make_router()
    route = router.route(START, FINISH)
    assert route.reached
    assert route.n_waypoints >= 2
    assert route.eta_hours > 0.0
    assert route.distance_nm > 0.0
    # one waypoint per isochrone level: time advances by dt
    assert route.time[0] == pytest.approx(0.0)
    assert np.all(np.diff(route.time) > 0.0)
    # leg properties derive from the geometry; the start waypoint has
    # no arriving leg
    assert np.isnan(route.heading[0])
    assert np.isnan(route.speed[0])
    assert np.isfinite(route.speed[1:]).all()
    # wind is sampled from the bound grid, never stored on the route
    tws, twa = wind_along_route(grid_from_dataset(router.weather), route)
    assert np.isfinite(tws[1:]).all()
    assert np.all(twa[1:] >= 0.0)
    assert np.all(twa[1:] <= 180.0)


def test_route_start_time_offsets_the_track():
    route = make_router().route(START, FINISH, start_time=6.0)
    assert route.time[0] == pytest.approx(6.0)
    assert route.eta_hours > 6.0


def test_horizon_exhaustion_returns_partial_route():
    router = LibWeatherRoutingRouter(
        weather=make_weather(),
        polar=synthetic_cruising_polar(),
        config=LibWeatherRoutingConfig(dt_hours=1.0, subdiv=5, max_hours=2.0),
    )
    route = router.route(START, FINISH)
    assert not route.reached
    assert np.isnan(route.eta_hours)
    assert route.n_waypoints >= 1


def test_departure_outside_forecast_returns_partial_route():
    router = make_router()
    # the synthetic grid covers hours 0..48; departing at its edge leaves
    # no weather for even one step
    route = router.route(START, FINISH, start_time=48.0)
    assert not route.reached
    assert route.n_waypoints == 1
    assert np.isnan(route.eta_hours)


def test_for_weather_binds_and_satisfies_protocol():
    weather = make_weather()
    router = LibWeatherRoutingRouter(
        polar=synthetic_cruising_polar(),
        config=LibWeatherRoutingConfig(dt_hours=1.0, subdiv=5, max_hours=48.0),
    )
    assert router.weather is None  # unbound setup carries no weather
    rebound = router.for_weather(weather)
    assert isinstance(rebound, Router)
    assert rebound is not router
    assert rebound.weather is weather
