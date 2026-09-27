import numpy as np
import pytest

from light_router.isochrone import IsochroneRouter, RouterConfig
from light_router.metrics import compare_routes
from light_router.polar import synthetic_cruising_polar
from light_router.staircase import STAIRCASE, run_staircase, write_csv
from light_router.synthetic import add_storm, trade_wind_field

START = (28.0, -15.5)
FINISH = (16.75, -22.9)


def make_router(grid):
    config = RouterConfig(
        dt_hours=2.0,
        n_headings=24,
        bin_deg=1.0,
        max_points=600,
        finish_radius_nm=30.0,
        max_hours=200.0,
    )
    return IsochroneRouter(grid=grid, polar=synthetic_cruising_polar(), config=config)


@pytest.fixture
def grid():
    lats = np.arange(10.0, 32.01, 0.5)
    lons = np.arange(-28.0, -12.99, 0.5)
    times = np.arange(0.0, 201.0, 6.0)
    field = trade_wind_field(
        lats, lons, times, mean_speed_kt=15.0, direction_from_deg=60.0
    )
    # add meridional gradient + small-scale spatial structure so coarse
    # sampling loses real information (uniform fields degrade for free)
    factor = 1.0 + 0.6 * (lats - lats[0]) / (lats[-1] - lats[0])
    wave = 1.0 + 0.25 * np.sin(lons[None, :] * 5.0) * np.sin(lats[:, None] * 7.0)
    modulation = (factor[:, None] * wave)[None, :, :]
    for name in ("u10", "v10"):
        field.data[name] = (field.data[name] * modulation).astype(np.float32)
    # overlay a compact storm (strong SW headwind) pulsing in time, sitting
    # on the direct route: the reference route must dodge it, and coarse
    # sampling misplaces or smears the dodge — smooth fields degrade for
    # free, so the degradation assertion needs a genuinely hard field
    return add_storm(field)


def test_staircase_runs_all_levels(grid):
    router = make_router(grid)
    rows = run_staircase(grid, router, START, FINISH)
    assert len(rows) == len(STAIRCASE)
    # unlimited row has full fidelity
    assert rows[0].spatial_stride == 1 and rows[0].bits == 32
    # every package fits its budget
    for row in rows:
        if row.budget_bytes is not None:
            assert row.package_bytes <= row.budget_bytes


def test_unlimited_row_matches_reference(grid):
    router = make_router(grid)
    rows = run_staircase(grid, router, START, FINISH)
    first = rows[0]
    assert first.metrics.eta_diff_pct == pytest.approx(0.0, abs=1e-6)
    assert first.metrics.distance_diff_pct == pytest.approx(0.0, abs=1e-6)
    assert not first.metrics.decision_divergence


def test_degradation_grows_as_budget_shrinks(grid):
    router = make_router(grid)
    rows = run_staircase(grid, router, START, FINISH)
    # the 1 KB row must be strictly worse than the unlimited row on at least
    # one reported metric (ETA or geographic divergence)
    worst = rows[-1]
    best = rows[0]
    worse = (
        worst.metrics.eta_diff_pct > best.metrics.eta_diff_pct + 1.0
        or worst.metrics.geographic_divergence_nm
        > best.metrics.geographic_divergence_nm + 10.0
    )
    assert worse


def test_write_csv(tmp_path, grid):
    router = make_router(grid)
    rows = run_staircase(grid, router, START, FINISH)
    out = tmp_path / "curve.csv"
    write_csv(rows, out)
    content = out.read_text().splitlines()
    assert len(content) == len(rows) + 1
    assert "eta_diff_pct" in content[0]
    assert "unlimited" in content[1]


def test_compare_routes_identity(grid):
    router = make_router(grid)
    route = router.route(START, FINISH)
    metrics = compare_routes(route, route, FINISH)
    assert metrics.eta_diff_pct == pytest.approx(0.0)
    assert metrics.distance_diff_pct == pytest.approx(0.0)
    assert metrics.geographic_divergence_nm == pytest.approx(0.0)
    assert not metrics.decision_divergence
