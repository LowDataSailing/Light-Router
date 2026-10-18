"""Artifacts increment: run directory, manifest, route export, plots, summarize.

Covers issues #6-#9 (specs/goal-1-baseline.md section 7). The staircase runs
once per module (fixture) on a small grid to keep the suite fast.
"""

from __future__ import annotations

import json

import numpy as np
import pytest

from experiments.reporting.artifacts import (
    MANIFEST_NAME,
    METRICS_NAME,
    budget_slug,
    git_sha,
    grid_checksum,
    new_run_dir,
    write_artifacts,
)
from light_router.dataset import to_cf_dataset
from light_router.routing import IsochroneRouter
from experiments.synthetic_polar import synthetic_cruising_polar
from experiments.harness.staircase import run_staircase
from experiments.synthetic import add_storm, trade_wind_field

START = (28.0, -15.5)
FINISH = (16.75, -22.9)
STAIRCASE = [None, 100_000, 10_000, 1_000]


def make_grid():
    lats = np.arange(12.0, 32.01, 1.0)
    lons = np.arange(-26.0, -12.99, 1.0)
    times = np.arange(0.0, 201.0, 12.0)
    field = trade_wind_field(
        lats, lons, times, mean_speed_kt=15.0, direction_from_deg=45.0
    )
    factor = 1.0 + 0.5 * (lats - lats[0]) / (lats[-1] - lats[0])
    wave = 1.0 + 0.25 * np.sin(lons[None, :] * 4.0) * np.sin(lats[:, None] * 6.0)
    modulation = (factor[:, None] * wave)[None, :, :]
    for name in ("u10", "v10"):
        field.data[name] = (field.data[name] * modulation).astype(np.float32)
    return add_storm(field)


@pytest.fixture(scope="module")
def result():
    grid = make_grid()
    weather = to_cf_dataset(grid)
    router = IsochroneRouter.from_dataset(
        weather,
        synthetic_cruising_polar(),
        dt_hours=4.0,
        n_headings=18,
        bin_deg=2.0,
        max_points=400,
        finish_radius_nm=40.0,
        max_hours=250.0,
    )
    return weather, router, run_staircase(weather, router, START, FINISH, STAIRCASE)


@pytest.fixture(scope="module")
def run_dir(result, tmp_path_factory):
    weather, router, staircase = result
    base = tmp_path_factory.mktemp("runs")
    run_dir = new_run_dir(base, "synthetic_canaries_cv")
    write_artifacts(
        run_dir,
        staircase,
        weather,
        scenario="synthetic_canaries_cv",
        start=START,
        finish=FINISH,
        router_config=router.config_as_dict(),
        staircase=STAIRCASE,
        source={"type": "synthetic"},
    )
    return run_dir


# --- ticket #6: run directory + manifest ------------------------------------


def test_git_sha_short():
    sha = git_sha()
    assert sha == "unknown" or 7 <= len(sha) <= 12


def test_grid_checksum_deterministic(result):
    weather = result[0]
    assert grid_checksum(weather) == grid_checksum(weather)
    other = to_cf_dataset(make_grid())
    other["u10"] = other["u10"] + 0.1
    assert grid_checksum(weather) != grid_checksum(other)


def test_new_run_dir_layout(tmp_path):
    run_dir = new_run_dir(tmp_path, "scenario_a", sha="deadbee")
    assert run_dir.exists()
    assert run_dir.parent.name == "scenario_a"
    assert run_dir.name.startswith("20")
    assert run_dir.name.endswith("-deadbee")


def test_run_dir_contents(run_dir, result):
    staircase = result[2]
    names = {p.name for p in run_dir.iterdir()}
    assert MANIFEST_NAME in names
    assert METRICS_NAME in names
    assert "wind_snapshot.npz" in names
    assert "route_reference.gpx" in names
    assert "route_reference.geojson" in names
    for row in staircase.rows:
        slug = budget_slug(row.budget)
        assert f"route_{slug}.gpx" in names
        assert f"route_{slug}.geojson" in names


def test_manifest_fields(run_dir):
    manifest = json.loads((run_dir / MANIFEST_NAME).read_text())
    assert manifest["schema_version"] == 1
    assert manifest["scenario"] == "synthetic_canaries_cv"
    # code version matches the run directory name suffix
    assert manifest["code_version"] == run_dir.name.rsplit("-", 1)[-1]
    assert len(manifest["data_checksum"]) == 64
    assert manifest["source"]["type"] == "synthetic"
    assert manifest["route"]["start"] == list(START)
    assert manifest["router_config"]["dt_hours"] == 4.0
    assert manifest["staircase"] == STAIRCASE
    assert manifest["grid"]["variables"] == ["u10", "v10"]


def test_metrics_csv_in_run_dir(run_dir, result):
    lines = (run_dir / METRICS_NAME).read_text().splitlines()
    assert lines[0].startswith("budget,budget_bytes,package_bytes")
    assert len(lines) == len(result[2].rows) + 1


# --- ticket #7: GPX + GeoJSON export -----------------------------------------


def test_gpx_roundtrip(run_dir):
    gpxpy = pytest.importorskip("gpxpy")
    gpx = gpxpy.parse((run_dir / "route_reference.gpx").read_text())
    assert len(gpx.tracks) == 1
    points = gpx.tracks[0].segments[0].points
    assert len(points) >= 2
    assert -90 <= points[0].latitude <= 90
    assert -180 <= points[0].longitude <= 180


def test_geojson_structure(run_dir):
    feature = json.loads((run_dir / "route_reference.geojson").read_text())
    assert feature["type"] == "Feature"
    assert feature["geometry"]["type"] == "LineString"
    coords = feature["geometry"]["coordinates"]
    assert len(coords) >= 2
    assert all(len(c) == 2 for c in coords)
    assert feature["properties"]["name"] == "route_reference"
    assert len(feature["points"]) == len(coords)


# --- issue #23: no bare NaN tokens in exported GeoJSON ------------------------


def test_geojson_strict_parse(run_dir):
    """Exported GeoJSON must parse with a strict JSON parser.

    Waypoint 0 is NaN-padded by convention; bare NaN tokens are invalid
    JSON (browsers, jq reject them), so they must serialize as null.
    """

    def reject(constant):
        raise ValueError(f"bare {constant} token")

    text = (run_dir / "route_reference.geojson").read_text()
    feature = json.loads(text, parse_constant=reject)
    assert feature["points"][0]["heading_deg"] is None


def test_geojson_unreached_route_exports_nulls():
    """An unreached route (NaN eta) exports nulls, not NaN.

    ``distance_nm`` is derived from the waypoint geometry, so a partial
    track still has a sailed distance; only the arrival time is null.
    """
    from experiments.reporting.export import route_to_geojson
    from light_router.models.route import Route, Waypoint

    route = Route(
        waypoints=[
            Waypoint(lat=28.0, lon=-15.5, time=0.0),
            Waypoint(lat=27.0, lon=-16.0, time=4.0),
        ],
        reached=False,
    )
    feature = route_to_geojson(route, "unreached")
    assert feature["properties"]["eta_hours"] is None
    assert feature["properties"]["distance_nm"] > 0.0
    # waypoint 0 has no arriving leg: derived speed/heading are null
    assert feature["points"][0]["speed_kt"] is None
    assert feature["points"][0]["heading_deg"] is None
    # leg speed is derived from the waypoint geometry (1 deg / 4 h)
    assert feature["points"][1]["speed_kt"] > 0.0
    # wind is sampled from a grid when given, null without one
    assert feature["points"][1]["tws_kt"] is None
    json.dumps(feature, allow_nan=False)


def test_geojson_samples_wind_when_weather_given():
    """Per-point wind comes from the grid the route is sampled against."""
    from experiments.reporting.export import route_to_geojson
    from light_router.dataset import grid_from_dataset
    from light_router.models.route import Route, Waypoint

    route = Route(
        waypoints=[
            Waypoint(lat=28.0, lon=-15.5, time=0.0),
            Waypoint(lat=27.0, lon=-16.0, time=4.0),
        ],
        reached=True,
    )
    grid = grid_from_dataset(make_grid_result_weather())
    feature = route_to_geojson(route, "sampled", weather=grid)
    assert feature["points"][1]["tws_kt"] is not None
    assert feature["points"][0]["twa_deg"] is None  # no arriving leg
    json.dumps(feature, allow_nan=False)


def make_grid_result_weather():
    """A small CF weather dataset for GeoJSON wind-sampling tests."""
    from light_router.dataset import to_cf_dataset
    from experiments.synthetic import trade_wind_field

    lats = np.arange(25.0, 30.01, 1.0)
    lons = np.arange(-18.0, -13.99, 1.0)
    times = np.arange(0.0, 13.0, 6.0)
    return to_cf_dataset(
        trade_wind_field(lats, lons, times, mean_speed_kt=15.0, direction_from_deg=45.0)
    )


# --- ticket #8: plots ---------------------------------------------------------


def test_plots_written(run_dir):
    pytest.importorskip("matplotlib")
    for name in (
        "plot_tracks.png",
        "plot_degradation.png",
        "plot_size_fidelity.png",
    ):
        path = run_dir / name
        assert path.exists(), f"{name} missing"
        assert path.stat().st_size > 0


# --- ticket #9: summarize ------------------------------------------------------


def test_summarize_rerenders(run_dir, capsys):
    pytest.importorskip("matplotlib")
    from experiments.reporting.summarize import summarize

    # plots exist from write_artifacts; remove one to prove re-render
    (run_dir / "plot_degradation.png").unlink()
    summarize(run_dir)
    assert (run_dir / "plot_degradation.png").exists()
    out = capsys.readouterr().out
    assert "scenario: synthetic_canaries_cv" in out
    assert "unlimited" in out


def test_summarize_cli_errors(tmp_path, capsys):
    from experiments.reporting.summarize import main

    assert main([str(tmp_path / "nope")]) == 1
    assert main([]) == 2
