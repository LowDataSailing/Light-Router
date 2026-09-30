import numpy as np
import pytest

from light_router.geo import destination, great_circle_distance, initial_bearing


def test_distance_known_value():
    # Canary Islands -> Cape Verde, ~790 nm
    d = great_circle_distance(28.0, -15.5, 16.75, -22.9)
    assert 770 < d < 810


def test_distance_zero():
    assert great_circle_distance(10.0, 20.0, 10.0, 20.0) == 0.0


def test_bearing_north():
    assert initial_bearing(10.0, 0.0, 12.0, 0.0) == pytest.approx(0.0, abs=0.1)


def test_bearing_east():
    assert initial_bearing(0.0, 10.0, 0.0, 12.0) == pytest.approx(90.0, abs=0.1)


def test_destination_roundtrip():
    lat, lon = destination(28.0, -15.5, 123.0, 100.0)
    d = great_circle_distance(28.0, -15.5, lat, lon)
    assert d == pytest.approx(100.0, abs=0.5)
    # bearing from start to destination matches the requested bearing
    assert initial_bearing(28.0, -15.5, lat, lon) == pytest.approx(123.0, abs=0.5)


def test_destination_vectorized():
    lats, lons = destination(
        np.array([0.0, 10.0]),
        np.array([0.0, 0.0]),
        np.array([90.0, 180.0]),
        np.array([60.0, 120.0]),
    )
    assert lats.shape == (2,)
    assert lons.shape == (2,)
