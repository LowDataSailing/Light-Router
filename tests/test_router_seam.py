"""Router seam v2: Waypoint/Route geometry, sampling, binding, compression."""

from __future__ import annotations

import numpy as np
import pytest

from light_router.dataset import to_cf_dataset
from light_router.models.route import Route, Waypoint
from light_router.models.weather import WeatherGrid
from light_router.routing import IsochroneRouter, Router
from light_router.sampling import wind_along_route, wind_along_track
from experiments.harness.degrade import (
    CompressedPackage,
    budget_staircase_compression,
)
from experiments.synthetic import trade_wind_field
from experiments.synthetic_polar import synthetic_cruising_polar


def make_grid() -> WeatherGrid:
    lats = np.arange(25.0, 30.01, 0.5)
    lons = np.arange(-18.0, -13.99, 0.5)
    times = np.arange(0.0, 49.0, 6.0)
    return trade_wind_field(
        lats, lons, times, mean_speed_kt=15.0, direction_from_deg=45.0
    )


def make_route() -> Route:
    """Two legs due south: 1 deg latitude over 4 h each."""
    return Route(
        waypoints=[
            Waypoint(lat=28.0, lon=-15.5, time=0.0),
            Waypoint(lat=27.0, lon=-15.5, time=4.0),
            Waypoint(lat=26.0, lon=-15.5, time=8.0),
        ],
        reached=True,
        eta_hours=8.0,
        distance_nm=120.0,
    )


# --- Waypoint + Route: geometry only, everything else derived -----------------


def test_route_is_waypoints_only():
    route = make_route()
    assert all(isinstance(w, Waypoint) for w in route.waypoints)
    assert route.n_waypoints == 3
    assert not hasattr(route, "tws")  # wind is sampled, never stored
    np.testing.assert_allclose(route.lat, [28.0, 27.0, 26.0])
    np.testing.assert_allclose(route.time, [0.0, 4.0, 8.0])


def test_derived_leg_properties():
    route = make_route()
    # heading of the arriving leg; NaN at the start waypoint
    assert np.isnan(route.heading[0])
    np.testing.assert_allclose(route.heading[1:], [180.0, 180.0])
    # speed over ground of the arriving leg; NaN at the start waypoint
    assert np.isnan(route.speed[0])
    assert route.speed[1] == pytest.approx(15.0, rel=0.01)  # 60 nm / 4 h


def test_empty_route_derived_properties():
    route = Route(waypoints=[], reached=False, eta_hours=float("nan"), distance_nm=0.0)
    assert route.n_waypoints == 0
    assert route.heading.size == 0
    assert route.speed.size == 0


# --- sampling: link routes and tracks to weather ------------------------------


def test_wind_along_route_matches_grid():
    grid = make_grid()
    route = make_route()
    tws, twa = wind_along_route(grid, route)
    assert tws.shape == (3,)
    # the synthetic field is 15 kt +- 15% temporal modulation
    assert np.all((13.0 <= tws) & (tws <= 17.5))
    # no arriving leg at the start waypoint
    assert np.isnan(twa[0])
    assert np.all(~np.isnan(twa[1:]))


def test_wind_along_track_bare_arrays():
    grid = make_grid()
    lat = np.array([28.0, 27.0])
    lon = np.array([-15.5, -15.5])
    time = np.array([0.0, 4.0])
    tws, twa = wind_along_track(grid, lat, lon, time)
    assert tws.shape == (2,)
    assert np.isnan(twa[0])


# --- for_weather: binding on the protocol -------------------------------------


def test_for_weather_rebinds_and_satisfies_protocol():
    weather = to_cf_dataset(make_grid())
    router = IsochroneRouter.from_dataset(weather, synthetic_cruising_polar())
    assert isinstance(router, Router)
    rebound = router.for_weather(weather)
    assert isinstance(rebound, Router)
    assert rebound is not router
    assert rebound.polar is router.polar  # setup carried over
    assert rebound.config is router.config


def test_base_router_name_defaults_to_class_name():
    from light_router.routing.protocol import BaseRouter

    class MyRouter(BaseRouter):
        def route(self, start, finish, start_time=0.0):
            raise NotImplementedError

    assert MyRouter.name == "MyRouter"
    assert MyRouter().name == "MyRouter"
    assert IsochroneRouter.name == "isochrone-surrogate"


# --- compression seam: byte-honest by construction ---------------------------


def test_budget_staircase_compression_reports_measured_bytes():
    grid = make_grid()
    package = budget_staircase_compression(grid, 3000)
    assert isinstance(package, CompressedPackage)
    assert package.config is not None
    assert 0 < package.package_bytes <= 3000
    assert package.grid.lats[0] == grid.lats[0]  # degraded view of the same field


def test_compression_none_when_budget_unreachable():
    package = budget_staircase_compression(make_grid(), 1)
    assert package is None


def test_compression_unlimited_is_identity_config():
    package = budget_staircase_compression(make_grid(), None)
    assert package is not None
    assert package.package_bytes > 0
    assert package.config is not None
