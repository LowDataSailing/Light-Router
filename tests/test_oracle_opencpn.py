"""OpenCPN headless oracle adapter: stub-pinned WR_HEADLESS_* contract."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import numpy as np
import pytest

from light_router.dataset import to_cf_dataset
from light_router.geo import great_circle_distance
from light_router.routing import Router
from experiments.oracle.opencpn import (
    OPENCPN_ORACLE_BRANCH,
    OPENCPN_ORACLE_COMMIT,
    OPENCPN_ORACLE_PIN,
    OPENCPN_ORACLE_REPO,
    OpenCPNConfig,
    OpenCPNRouter,
    build_scenario,
    parse_result,
)
from experiments.synthetic import SYNTHETIC_EPOCH, trade_wind_field
from experiments.synthetic_polar import synthetic_cruising_polar

STUB_SOURCE = Path(__file__).parent / "wr_headless_stub.py"
START = (28.0, -15.5)
FINISH = (16.75, -22.9)


def make_weather():
    lats = np.arange(12.0, 32.01, 1.0)
    lons = np.arange(-26.0, -12.99, 1.0)
    times = np.arange(0.0, 121.0, 6.0)
    return to_cf_dataset(trade_wind_field(lats, lons, times))


@pytest.fixture
def stub_binary(tmp_path: Path) -> Path:
    """Executable copy of the stub binary (the adapter runs it directly)."""
    binary = tmp_path / "opencpn-stub"
    shutil.copy(STUB_SOURCE, binary)
    binary.chmod(0o755)
    return binary


def make_router(stub_binary: Path, tmp_path: Path) -> OpenCPNRouter:
    return OpenCPNRouter(
        binary=stub_binary,
        weather=make_weather(),
        polar=synthetic_cruising_polar(),
        workdir=tmp_path / "work",
    )


def test_pin_records_repo_branch_and_commit():
    assert OPENCPN_ORACLE_REPO == "https://github.com/pob220/weather_routing_pi"
    assert OPENCPN_ORACLE_BRANCH == "routing-engine-refactor"
    assert len(OPENCPN_ORACLE_COMMIT) == 40
    assert OPENCPN_ORACLE_PIN == (
        f"{OPENCPN_ORACLE_REPO}@{OPENCPN_ORACLE_BRANCH}@{OPENCPN_ORACLE_COMMIT}"
    )


def test_name_attribute_carries_the_pin(stub_binary, tmp_path):
    router = make_router(stub_binary, tmp_path)
    assert router.name.startswith("opencpn-weather-routing@")
    assert OPENCPN_ORACLE_COMMIT in router.name
    assert OPENCPN_ORACLE_BRANCH in router.name


def test_missing_binary_raises_informative_error(tmp_path):
    router = OpenCPNRouter(
        binary=tmp_path / "nonexistent-opencpn",
        weather=make_weather(),
        polar=synthetic_cruising_polar(),
    )
    with pytest.raises(RuntimeError) as excinfo:
        router.route(START, FINISH)
    message = str(excinfo.value)
    assert OPENCPN_ORACLE_PIN in message
    assert "docs/headless_scenarios.md" in message
    assert "out of scope" in message


def test_route_writes_the_scenario_contract(stub_binary, tmp_path):
    router = make_router(stub_binary, tmp_path)
    router.route(START, FINISH, start_time=6.0)

    scenario = json.loads((tmp_path / "work" / "scenario.json").read_text())
    assert scenario["schemaVersion"] == 1
    assert scenario["start"] == {"name": "start", "lat": START[0], "lon": START[1]}
    assert scenario["end"] == {"name": "finish", "lat": FINISH[0], "lon": FINISH[1]}
    # start_time 6 h after the synthetic epoch, ISO UTC
    assert scenario["startTime"] == "2026-01-01T06:00:00Z"
    assert scenario["environment"] == {"useCurrents": False, "useGrib": True}
    route = scenario["route"]
    assert route["boatFile"].endswith("polar.csv")
    assert route["timeStepSeconds"] == 3600
    assert route["headingFromDegrees"] == 0.0
    assert route["headingToDegrees"] == 360.0
    assert route["headingStepDegrees"] == 5.0
    assert route["maxTrueWindKnots"] == 60.0
    assert route["maxApparentWindKnots"] == 60.0
    assert route["routingEffortPercent"] == 100
    safety = scenario["safety"]
    assert safety["mode"] == "none"
    assert safety["enforce"] is False
    assert safety["landMarginNm"] == 0.0
    assert safety["minimumDepthM"] == 0.0


def test_route_writes_wind_field_and_polar(stub_binary, tmp_path):
    router = make_router(stub_binary, tmp_path)
    weather = router.weather
    router.route(START, FINISH)

    wind = json.loads((tmp_path / "work" / "wind_field.json").read_text())
    assert len(wind["lats"]) == weather.sizes["latitude"]
    assert len(wind["lons"]) == weather.sizes["longitude"]
    assert len(wind["times_hours"]) == weather.sizes["time"]
    assert len(wind["u10_ms"]) == weather.sizes["time"]
    polar_csv = (tmp_path / "work" / "polar.csv").read_text()
    assert polar_csv.startswith("TWA\\TWS")


def test_stub_result_parsed_into_route(stub_binary, tmp_path):
    router = make_router(stub_binary, tmp_path)
    route = router.route(START, FINISH, start_time=6.0)
    result = json.loads((tmp_path / "work" / "result.json").read_text())

    assert isinstance(router, Router)
    assert route.reached
    # the headless runner exposes no track: endpoints only
    assert route.n_waypoints == 2
    assert (route.lat[0], route.lon[0]) == START
    assert (route.lat[1], route.lon[1]) == FINISH
    assert route.time[0] == 6.0
    candidate = result["candidates"][0]
    assert route.eta_hours == pytest.approx(6.0 + candidate["elapsed"] / 3600.0)
    # no track: the derived distance is the endpoints' great-circle, not
    # the runner's reported sailed distanceNm
    assert route.distance_nm == pytest.approx(
        great_circle_distance(START[0], START[1], FINISH[0], FINISH[1])
    )
    assert np.isnan(route.speed[0])  # no arriving leg at the start
    assert route.speed[1] == pytest.approx(route.distance_nm / (route.eta_hours - 6.0))


def test_stub_failure_result_is_partial_route(stub_binary, tmp_path, monkeypatch):
    monkeypatch.setenv("WR_STUB_RESULT_MODE", "failed")
    router = make_router(stub_binary, tmp_path)
    route = router.route(START, FINISH)

    assert not route.reached
    assert route.n_waypoints == 1
    assert (route.lat[0], route.lon[0]) == START
    assert np.isnan(route.eta_hours)
    assert route.distance_nm == 0.0


def test_parse_result_rejects_incomplete_status():
    payload = {
        "schemaVersion": 1,
        "status": "failed",
        "failureReason": "no_completed_routes",
        "candidates": [],
        "diagnostics": {},
    }
    route = parse_result(payload, START, FINISH, 0.0)
    assert not route.reached


def test_parse_result_picks_fastest_completed_candidate():
    payload = {
        "schemaVersion": 1,
        "status": "complete",
        "candidates": [
            {"state": "complete", "elapsed": 40000, "distanceNm": 300.0},
            {"state": "complete", "elapsed": 36000, "distanceNm": 290.0},
            {"state": "failed", "elapsed": 50000, "distanceNm": 400.0},
        ],
        "diagnostics": {},
    }
    route = parse_result(payload, START, FINISH, 2.0)
    assert route.reached
    assert route.eta_hours == pytest.approx(2.0 + 36000 / 3600.0)
    # distanceNm is contract-validated but not representable without a
    # track; the derived distance is the endpoints' great-circle
    assert route.distance_nm == pytest.approx(
        great_circle_distance(START[0], START[1], FINISH[0], FINISH[1])
    )


def test_build_scenario_carries_custom_config():
    config = OpenCPNConfig(
        time_step_seconds=7200,
        heading_step_deg=10.0,
        max_true_wind_knots=35.0,
        routing_effort_percent=200,
        safety_mode="gshhs",
        safety_enforce=True,
        land_margin_nm=5.0,
        minimum_depth_m=2.0,
    )
    scenario = build_scenario(START, FINISH, SYNTHETIC_EPOCH, Path("/b/p.csv"), config)
    assert scenario["route"]["timeStepSeconds"] == 7200
    assert scenario["route"]["headingStepDegrees"] == 10.0
    assert scenario["route"]["maxTrueWindKnots"] == 35.0
    assert scenario["route"]["routingEffortPercent"] == 200
    assert scenario["safety"]["mode"] == "gshhs"
    assert scenario["safety"]["enforce"] is True
    assert scenario["safety"]["landMarginNm"] == 5.0
    assert scenario["safety"]["minimumDepthM"] == 2.0


def test_config_rejects_invalid_values():
    with pytest.raises(ValueError, match="routing_effort_percent"):
        OpenCPNConfig(routing_effort_percent=300)
    with pytest.raises(ValueError, match="safety_mode"):
        OpenCPNConfig(safety_mode="bogus")
    with pytest.raises(ValueError, match="time_step_seconds"):
        OpenCPNConfig(time_step_seconds=0)


def test_for_weather_binds_and_satisfies_protocol(stub_binary, tmp_path):
    weather = make_weather()
    router = OpenCPNRouter(
        binary=stub_binary,
        polar=synthetic_cruising_polar(),
        workdir=tmp_path / "work",
    )
    assert router.weather is None  # unbound setup carries no weather
    rebound = router.for_weather(weather)
    assert isinstance(rebound, Router)
    assert rebound is not router
    assert rebound.weather is weather
    route = rebound.route(START, FINISH, start_time=48.0)
    assert route.reached  # the stub always completes the great circle
    assert route.n_waypoints == 2
    assert route.eta_hours > 48.0
