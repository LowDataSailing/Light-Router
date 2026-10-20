"""Validation harness: surrogate bias against whichever oracle is available."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import numpy as np
import pytest

from light_router.dataset import to_cf_dataset
from experiments.oracle.opencpn import OpenCPNRouter
from experiments.oracle.validate import (
    available_oracles,
    format_report,
    run_validation,
    validate_surrogate,
)
from experiments.synthetic import trade_wind_field
from experiments.synthetic_polar import synthetic_cruising_polar

STUB_SOURCE = Path(__file__).parent / "wr_headless_stub.py"
START = (28.0, -15.5)
FINISH = (26.0, -15.9)

SURROGATE_KWARGS = dict(
    dt_hours=2.0,
    n_headings=18,
    bin_deg=1.0,
    max_points=400,
    finish_radius_nm=10.0,
    max_hours=48.0,
)


def make_weather():
    lats = np.arange(24.0, 30.01, 0.5)
    lons = np.arange(-18.0, -13.99, 0.5)
    times = np.arange(0.0, 49.0, 6.0)
    return to_cf_dataset(trade_wind_field(lats, lons, times))


@pytest.fixture
def stub_binary(tmp_path: Path) -> Path:
    binary = tmp_path / "opencpn-stub"
    shutil.copy(STUB_SOURCE, binary)
    binary.chmod(0o755)
    return binary


def test_validate_surrogate_against_stub_oracle(stub_binary):
    oracle = OpenCPNRouter(binary=stub_binary, polar=synthetic_cruising_polar())
    report = validate_surrogate(
        make_weather(),
        START,
        FINISH,
        synthetic_cruising_polar(),
        oracle,
        surrogate_kwargs=SURROGATE_KWARGS,
    )
    assert report["oracle"].startswith("opencpn-weather-routing@")
    assert report["surrogate"] == "IsochroneRouter"
    assert report["oracle_reached"]
    assert report["surrogate_reached"]
    # the stub oracle exposes endpoints only; the report records that
    assert report["oracle_track_waypoints"] == 2
    assert report["eta_bias_pct"] == pytest.approx(
        (report["surrogate_eta_hours"] - report["oracle_eta_hours"])
        / report["oracle_eta_hours"]
        * 100.0
    )
    assert np.isfinite(report["distance_bias_pct"])
    assert np.isfinite(report["geographic_divergence_nm"])


def test_validate_surrogate_against_libweatherrouting():
    pytest.importorskip(
        "weatherrouting", reason="optional 'oracle' group not installed"
    )
    from experiments.oracle.libweatherrouting import (
        LibWeatherRoutingConfig,
        LibWeatherRoutingRouter,
    )

    oracle = LibWeatherRoutingRouter(
        polar=synthetic_cruising_polar(),
        config=LibWeatherRoutingConfig(dt_hours=1.0, subdiv=5, max_hours=48.0),
    )
    report = validate_surrogate(
        make_weather(),
        START,
        FINISH,
        synthetic_cruising_polar(),
        oracle,
        surrogate_kwargs=SURROGATE_KWARGS,
    )
    assert report["oracle"].startswith("libweatherrouting@")
    assert report["oracle_reached"]
    assert report["surrogate_reached"]
    assert report["oracle_track_waypoints"] > 2  # a real track
    assert np.isfinite(report["eta_bias_pct"])
    assert np.isfinite(report["geographic_divergence_nm"])


def test_validate_surrogate_reports_unreached_oracle(stub_binary, monkeypatch):
    monkeypatch.setenv("WR_STUB_RESULT_MODE", "failed")
    oracle = OpenCPNRouter(binary=stub_binary, polar=synthetic_cruising_polar())
    report = validate_surrogate(
        make_weather(),
        START,
        FINISH,
        synthetic_cruising_polar(),
        oracle,
        surrogate_kwargs=SURROGATE_KWARGS,
    )
    assert report["oracle_reached"] is False
    assert "no reference" in report["reason"]
    assert "eta_bias_pct" not in report


def test_run_validation_degrades_gracefully_without_oracles(tmp_path):
    output = tmp_path / "bias_report.json"
    report = run_validation(
        oracles=[],
        output=output,
        surrogate_kwargs=SURROGATE_KWARGS,
    )
    assert report["oracles"] == []
    assert "no oracle available" in report["reason"]
    assert "oracles" in json.loads(output.read_text())
    assert output.exists()
    assert "no oracle available" in format_report(report)


def test_available_oracles_finds_libweatherrouting_when_installed():
    pytest.importorskip(
        "weatherrouting", reason="optional 'oracle' group not installed"
    )
    oracles = available_oracles(synthetic_cruising_polar(), opencpn_binary=None)
    names = [name for name, _oracle in oracles]
    assert "libweatherrouting" in names


def test_available_oracles_skips_missing_opencpn_binary(tmp_path, monkeypatch):
    monkeypatch.setenv("LR_ORACLE_OPENCPN_BINARY", str(tmp_path / "absent"))
    oracles = available_oracles(synthetic_cruising_polar())
    names = [name for name, _oracle in oracles]
    assert "opencpn-weather-routing" not in names
