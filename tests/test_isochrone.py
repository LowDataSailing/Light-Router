import numpy as np

from light_router.routing import (
    IsochroneRouter,
    mean_vmg,
    route_bearing,
)
from experiments.synthetic_polar import synthetic_cruising_polar
from experiments.synthetic import add_storm, trade_wind_field


def make_router(wind_from_deg=60.0, dt=2.0, max_hours=200.0):
    lats = np.arange(10.0, 32.01, 0.5)
    lons = np.arange(-28.0, -12.99, 0.5)
    times = np.arange(0.0, max_hours + 1.0, 6.0)
    grid = trade_wind_field(
        lats, lons, times, mean_speed_kt=15.0, direction_from_deg=wind_from_deg
    )
    return IsochroneRouter(
        grid=grid,
        polar=synthetic_cruising_polar(),
        dt_hours=dt,
        n_headings=24,
        bin_deg=1.0,
        max_points=600,
        finish_radius_nm=30.0,
        max_hours=max_hours,
    )


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


# --- Decision #20: planning wind limit ---------------------------------------


def make_storm_router(max_tws_kt=None, max_hours=200.0):
    """Trade-wind field with the default storm parked on the direct route."""
    lats = np.arange(10.0, 32.01, 0.5)
    lons = np.arange(-28.0, -12.99, 0.5)
    times = np.arange(0.0, max_hours + 1.0, 6.0)
    grid = add_storm(
        trade_wind_field(lats, lons, times, mean_speed_kt=15.0, direction_from_deg=60.0)
    )
    return IsochroneRouter(
        grid=grid,
        polar=synthetic_cruising_polar(),
        dt_hours=2.0,
        n_headings=24,
        bin_deg=1.0,
        max_points=600,
        finish_radius_nm=30.0,
        max_hours=max_hours,
        max_tws_kt=max_tws_kt,
    )


def test_wind_limit_keeps_route_under_the_limit():
    from light_router.sampling import wind_along_route

    router = make_storm_router(max_tws_kt=25.0)
    route = router.route(START, FINISH)
    assert route.reached
    # no planned waypoint sits in wind above the limit (waypoint 0 is NaN-padded)
    tws, _ = wind_along_route(router.grid, route)
    assert np.nanmax(tws) <= 25.0 + 1e-6


def test_wind_limit_off_by_default():
    router = make_storm_router()
    route = router.route(START, FINISH)
    assert route.reached
    assert router.max_tws_kt is None
    assert router.config_as_dict()["max_tws_kt"] is None


def test_wind_limit_config_serializes():
    router = make_storm_router(max_tws_kt=25.0)
    assert router.config_as_dict()["max_tws_kt"] == 25.0


def test_wind_limit_below_traps_the_boat():
    # a limit under the trade-wind speed leaves nothing sailable
    router = make_storm_router(max_tws_kt=5.0)
    route = router.route(START, FINISH)
    assert not route.reached
