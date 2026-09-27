import numpy as np
import pytest

from light_router.synthetic import trade_wind_field
from light_router.weather import WeatherGrid, route_grid_box


def make_grid():
    lats = np.arange(10.0, 20.01, 0.5)
    lons = np.arange(-30.0, -14.99, 0.5)
    times = np.arange(0.0, 13.0, 3.0)
    return trade_wind_field(lats, lons, times, mean_speed_kt=15.0)


def test_grid_validation_rejects_decreasing_axes():
    with pytest.raises(ValueError):
        WeatherGrid(
            times=np.array([0.0, 3.0]),
            lats=np.array([10.0, 9.0]),
            lons=np.array([0.0, 1.0]),
            data={},
        )


def test_grid_validation_rejects_bad_shape():
    with pytest.raises(ValueError):
        WeatherGrid(
            times=np.array([0.0, 3.0]),
            lats=np.array([10.0, 11.0]),
            lons=np.array([0.0, 1.0]),
            data={"u10": np.zeros((2, 2, 3), dtype=np.float32)},
        )


def test_sample_at_grid_point_is_exact():
    grid = make_grid()
    u = grid.sample(0.0, grid.lats[2], grid.lons[3], "u10")
    assert u == pytest.approx(grid.data["u10"][0, 2, 3], abs=1e-5)


def test_sample_interpolates_linearly_in_time():
    grid = make_grid()
    u0 = grid.sample(0.0, 15.0, -20.0, "u10")
    u3 = grid.sample(3.0, 15.0, -20.0, "u10")
    u15 = grid.sample(1.5, 15.0, -20.0, "u10")
    assert u15 == pytest.approx((u0 + u3) / 2.0, abs=1e-4)


def test_sample_clamps_outside_grid():
    grid = make_grid()
    inside = grid.sample(6.0, 15.0, -20.0, "u10")
    assert grid.sample(6.0, 15.0, -500.0, "u10") == pytest.approx(inside, abs=1e-4)


def test_wind_speed_matches_field():
    grid = make_grid()
    speed, direction = grid.wind(np.array([0.0]), np.array([15.0]), np.array([-20.0]))
    assert speed[0] == pytest.approx(15.0, abs=0.2)  # 15 kt field
    assert direction[0] == pytest.approx(60.0, abs=1.0)  # trades from 60 deg


def test_route_grid_box_covers_both_ends():
    box = route_grid_box((28.0, -15.5), (16.75, -22.9), margin_deg=2.0)
    lon_min, lon_max, lat_min, lat_max = box
    assert lon_min <= -22.9 and lon_max >= -15.5
    assert lat_min <= 16.75 and lat_max >= 28.0
