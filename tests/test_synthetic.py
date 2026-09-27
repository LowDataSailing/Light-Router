import numpy as np
import pytest

from light_router.synthetic import add_storm, trade_wind_field


@pytest.fixture
def field():
    lats = np.arange(10.0, 32.01, 0.5)
    lons = np.arange(-28.0, -12.99, 0.5)
    times = np.arange(0.0, 49.0, 6.0)
    return trade_wind_field(
        lats, lons, times, mean_speed_kt=15.0, direction_from_deg=60.0
    )


def test_add_storm_returns_new_grid(field):
    before = field.data["u10"].copy()
    stormed = add_storm(field)
    assert stormed is not field
    np.testing.assert_array_equal(field.data["u10"], before)


def test_add_storm_peaks_at_center(field):
    stormed = add_storm(
        field, center=(22.5, -19.0), radius_deg=2.5, strength_ms=15.0, period_hours=48.0
    )
    # at the pulse maximum (t = 12 h for a 48 h period) the center is fully
    # blended toward the storm vector (15, 15) m/s
    t_idx = int(np.argmin(np.abs(field.times - 12.0)))
    lat_idx = int(np.argmin(np.abs(field.lats - 22.5)))
    lon_idx = int(np.argmin(np.abs(field.lons + 19.0)))
    u_center = stormed.data["u10"][t_idx, lat_idx, lon_idx]
    assert u_center == pytest.approx(15.0, abs=0.1)


def test_add_storm_far_away_unchanged(field):
    stormed = add_storm(field, center=(22.5, -19.0))
    far_lat = int(np.argmin(np.abs(field.lats - 11.0)))
    far_lon = int(np.argmin(np.abs(field.lons - 27.0)))
    np.testing.assert_allclose(
        stormed.data["u10"][:, far_lat, far_lon],
        field.data["u10"][:, far_lat, far_lon],
        atol=1e-3,
    )
