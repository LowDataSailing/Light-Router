"""Operational artifacts: run directory for the real-router-mimic passage."""

from __future__ import annotations

import json

import numpy as np
import pytest

from experiments.reporting.artifacts import (
    CYCLES_NAME,
    MANIFEST_NAME,
    PASSAGE_NAME,
    budget_slug,
    new_run_dir,
    write_operational_artifacts,
)
from experiments.harness.staircase import budget_label
from light_router.dataset import to_cf_dataset
from light_router.routing import IsochroneRouter
from experiments.synthetic_polar import synthetic_cruising_polar
from experiments.simulation.simulate import run_operational_staircase
from experiments.synthetic import trade_wind_field

START = (29.5, -13.5)
FINISH = (26.5, -16.5)
BUDGETS: list[int | None] = [None, 3000]

ROUTER_KWARGS = dict(
    dt_hours=2.0,
    n_headings=18,
    bin_deg=1.0,
    max_points=300,
    finish_radius_nm=15.0,
    max_hours=60.0,
)


def make_weather(wind_kt: float = 15.0):
    lats = np.arange(25.5, 30.51, 0.5)
    lons = np.arange(-17.5, -12.99, 0.5)
    times = np.arange(0.0, 49.0, 6.0)
    return to_cf_dataset(
        trade_wind_field(
            lats, lons, times, mean_speed_kt=wind_kt, direction_from_deg=45.0
        )
    )


@pytest.fixture(scope="module")
def results():
    from light_router.models.forecast import ForecastCycle

    weather = make_weather()
    cycles = [ForecastCycle(init_hour=h, weather=weather) for h in (0.0, 6.0, 12.0)]
    router = IsochroneRouter.from_dataset(
        weather, synthetic_cruising_polar(), **ROUTER_KWARGS
    )
    return (
        weather,
        run_operational_staircase(
            weather,
            cycles,
            START,
            FINISH,
            router,
            synthetic_cruising_polar(),
            BUDGETS,
            max_hours=60.0,
        ),
    )


@pytest.fixture(scope="module")
def run_dir(results, tmp_path_factory):
    weather, passage_results = results
    run_dir = new_run_dir(tmp_path_factory.mktemp("runs"), "operational_test")
    write_operational_artifacts(
        run_dir,
        passage_results,
        weather,
        scenario="operational_test",
        start=START,
        finish=FINISH,
        router_config=ROUTER_KWARGS,
        budgets=BUDGETS,
        source={"type": "operational", "truth": "synthetic"},
        plots=False,  # plots covered below with matplotlib present
        router="isochrone-surrogate",
        polar=synthetic_cruising_polar(),
        polar_source="synthetic_cruising_polar",
        price_per_kb=0.01,
    )
    return run_dir


def test_budget_labels():
    assert budget_label(None) == "unlimited"
    assert budget_label(3000) == "3 KB"
    assert budget_label(500) == "500 B"
    assert budget_slug(budget_label(None)) == "unlimited"


def test_passage_result_as_route(results):
    _, passage_results = results
    route = passage_results[0].as_route()
    assert route.n_waypoints == len(passage_results[0].time)
    # waypoint 0 is the start: no leg yet, per-leg arrays are NaN-padded
    assert np.isnan(route.heading[0]) and np.isnan(route.speed[0])
    assert route.reached == passage_results[0].reached
    assert route.eta_hours == passage_results[0].passage_hours


def test_operational_run_dir_contents(run_dir):
    names = {p.name for p in run_dir.iterdir()}
    assert MANIFEST_NAME in names
    assert PASSAGE_NAME in names
    assert CYCLES_NAME in names
    assert "wind_snapshot.npz" in names
    for budget in BUDGETS:
        slug = budget_slug(budget_label(budget))
        assert f"track_{slug}.gpx" in names
        assert f"track_{slug}.geojson" in names


def test_passage_csv_rows(run_dir, results):
    _, passage_results = results
    lines = (run_dir / PASSAGE_NAME).read_text().splitlines()
    assert lines[0] == (
        "budget,total_package_bytes,cost_eur,cycles,passage_hours,distance_nm,"
        "max_tws_kt,mean_tws_kt,pct_upwind,pct_downwind,"
        "compute_total_s,compute_mean_s,reached"
    )
    assert len(lines) == len(passage_results) + 1
    assert lines[1].startswith("unlimited,")
    # cost model (issue #14): delivered bytes priced at 0.01 EUR/KB
    row = lines[1].split(",")
    assert row[2] == f"{passage_results[0].total_package_bytes / 1000 * 0.01:.2f}"
    # experienced weather (issue #18) and compute time (issue #19) present
    assert 0.0 < float(row[6]) <= 40.0  # max_tws_kt
    assert 0.0 <= float(row[8]) <= 100.0  # pct_upwind
    assert float(row[10]) >= 0.0  # compute_total_s


def test_cycles_csv_rows(run_dir, results):
    _, passage_results = results
    lines = (run_dir / CYCLES_NAME).read_text().splitlines()
    assert lines[0] == (
        "budget,hour,spatial_stride,temporal_stride,bits,"
        "package_bytes,cumulative_bytes,plan_reached,planned_arrival_hour,"
        "planned_bearing_deg,plan_checksum,churn_nm,execution_error_nm,"
        "belief_error_h,forecast_error_kt,forecast_staleness_h,compute_s"
    )
    n_cycles = sum(len(r.cycles) for r in passage_results)
    assert len(lines) == n_cycles + 1
    assert "unlimited,0.0," in lines[1]
    # bandwidth ledger (issue #14): cumulative bytes never decrease per budget
    for result in passage_results:
        rows = [
            ln.split(",")
            for ln in lines[1:]
            if ln.startswith(budget_label(result.budget_bytes) + ",")
        ]
        cumulative = [int(r[6]) for r in rows]
        assert cumulative == sorted(cumulative)
        assert cumulative[-1] == result.total_package_bytes


def test_operational_manifest(run_dir):
    manifest = json.loads((run_dir / MANIFEST_NAME).read_text())
    assert manifest["scenario"] == "operational_test"
    assert manifest["staircase"] == BUDGETS
    assert manifest["source"]["truth"] == "synthetic"
    # routing-model identity (issue #16): algorithm + polar provenance
    assert manifest["router"]["algorithm"] == "isochrone-surrogate"
    assert manifest["polar"]["source"] == "synthetic_cruising_polar"
    assert manifest["polar"]["checksum"] == synthetic_cruising_polar().checksum


def test_operational_plots(tmp_path, results):
    pytest.importorskip("matplotlib")
    from experiments.reporting.plots import write_operational_plots

    weather, passage_results = results
    out = tmp_path / "plots"
    out.mkdir()
    write_operational_plots(out, passage_results, weather)
    for name in ("plot_tracks.png", "plot_passage_budget.png"):
        assert (out / name).stat().st_size > 0
