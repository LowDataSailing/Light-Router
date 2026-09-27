import numpy as np

from light_router.isochrone import (
    IsochroneRouter,
    RouterConfig,
    mean_vmg,
    route_bearing,
)
from light_router.polar import synthetic_cruising_polar
from light_router.synthetic import trade_wind_field


def make_router(wind_from_deg=60.0, dt=2.0, max_hours=200.0):
    lats = np.arange(10.0, 32.01, 0.5)
    lons = np.arange(-28.0, -12.99, 0.5)
    times = np.arange(0.0, max_hours + 1.0, 6.0)
    grid = trade_wind_field(
        lats, lons, times, mean_speed_kt=15.0, direction_from_deg=wind_from_deg
    )
    config = RouterConfig(
        dt_hours=dt,
        n_headings=24,
        bin_deg=1.0,
        max_points=600,
        finish_radius_nm=30.0,
        max_hours=max_hours,
    )
    return IsochroneRouter(grid=grid, polar=synthetic_cruising_polar(), config=config)


START = (28.0, -15.5)
FINISH = (16.75, -22.9)


def test_reaches_finish_with_sane_eta():
    router = make_router()
    route = router.route(START, FINISH)
    assert route.reached
    # ~740 nm at 6-7 kt -> 100-140 h; allow margin
    assert 80.0 < route.eta_hours < 180.0
    assert route.n_waypoints >= 2


def test_waypoints_progress_toward_finish():
    router = make_router()
    route = router.route(START, FINISH)
    from light_router.geo import great_circle_distance

    remaining = great_circle_distance(route.lat, route.lon, FINISH[0], FINISH[1])
    # remaining distance is non-increasing along the route (allow small noise)
    increases = np.diff(remaining)
    assert np.all(increases <= 5.0)


def test_distance_close_to_great_circle():
    router = make_router()
    route = router.route(START, FINISH)
    from light_router.geo import great_circle_distance

    gc = great_circle_distance(START[0], START[1], FINISH[0], FINISH[1])
    # a sailed route is longer than the great circle but not absurdly so
    assert gc * 0.95 < route.distance_nm < gc * 1.6


def test_partial_route_when_horizon_too_short():
    router = make_router(max_hours=10.0)
    route = router.route(START, FINISH)
    assert not route.reached
    assert np.isnan(route.eta_hours)
    assert route.n_waypoints >= 2


def test_trivial_route_when_start_at_finish():
    router = make_router()
    route = router.route(FINISH, FINISH)
    assert route.reached
    assert route.eta_hours == 0.0
    assert route.distance_nm == 0.0


def test_route_bearing_and_vmg():
    router = make_router()
    route = router.route(START, FINISH)
    bearing = route_bearing(route)
    assert not np.isnan(bearing)
    vmg = mean_vmg(route, FINISH)
    assert 0.0 < vmg <= 8.0  # positive progress, below hull speed
