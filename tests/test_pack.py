"""Data packs: self-contained scenario data, checksummed, rerunnable."""

from __future__ import annotations

import json

import numpy as np
import pytest

from light_router.data.pack import (
    PACK_MANIFEST,
    TRUTH_NAME,
    cycle_file_name,
    load_pack,
    write_pack,
)
from light_router.dataset import grid_from_dataset, to_cf_dataset
from light_router.simulate import ForecastCycle
from light_router.synthetic import trade_wind_field


def make_weather(lats, lons, times, wind_kt=15.0):
    return to_cf_dataset(
        trade_wind_field(
            lats, lons, times, mean_speed_kt=wind_kt, direction_from_deg=45.0
        )
    )


@pytest.fixture()
def scenario_data():
    truth = make_weather(
        np.arange(25.0, 30.01, 0.5),
        np.arange(-17.0, -12.99, 0.5),
        np.arange(0.0, 49.0, 6.0),
    )
    cycles = [
        ForecastCycle(
            init_hour=h,
            weather=make_weather(
                np.arange(25.0, 30.01, 0.5),
                np.arange(-17.0, -12.99, 0.5),
                np.arange(0.0, 25.0, 6.0),
            ),
        )
        for h in (12.0, 0.0, 6.0)  # unsorted on purpose
    ]
    return truth, cycles


def test_pack_roundtrip(tmp_path, scenario_data):
    truth, cycles = scenario_data
    pack_dir = write_pack(
        tmp_path / "pack",
        scenario="test_scenario",
        truth=truth,
        cycles=cycles,
        source={"truth": "synthetic"},
    )
    names = {p.name for p in pack_dir.iterdir()}
    assert PACK_MANIFEST in names
    assert TRUTH_NAME in names
    assert cycle_file_name(0.0) in names
    assert cycle_file_name(6.0) in names
    assert cycle_file_name(12.0) in names

    loaded_truth, loaded_cycles = load_pack(pack_dir)
    # cycles come back sorted by init_hour
    assert [c.init_hour for c in loaded_cycles] == [0.0, 6.0, 12.0]
    # the canonical CF contract holds on everything loaded
    grid_from_dataset(loaded_truth)
    for cycle in loaded_cycles:
        grid_from_dataset(cycle.weather)
    # data survived the roundtrip
    assert loaded_truth["u10"].shape == truth["u10"].shape
    np.testing.assert_allclose(
        loaded_truth["u10"].values, truth["u10"].values, rtol=1e-6
    )
    np.testing.assert_allclose(
        loaded_cycles[0].weather["v10"].values,
        cycles[1].weather["v10"].values,
        rtol=1e-6,
    )


def test_pack_manifest_fields(tmp_path, scenario_data):
    truth, cycles = scenario_data
    pack_dir = write_pack(
        tmp_path / "pack",
        scenario="test_scenario",
        truth=truth,
        cycles=cycles,
        source={"truth": "synthetic"},
    )
    manifest = json.loads((pack_dir / PACK_MANIFEST).read_text())
    assert manifest["schema_version"] == 1
    assert manifest["scenario"] == "test_scenario"
    assert manifest["truth_file"] == TRUTH_NAME
    assert len(manifest["cycles"]) == 3
    assert set(manifest["files_sha256"]) == {
        TRUTH_NAME,
        cycle_file_name(0.0),
        cycle_file_name(6.0),
        cycle_file_name(12.0),
    }
    assert all(len(v) == 64 for v in manifest["files_sha256"].values())


def test_pack_detects_corruption(tmp_path, scenario_data):
    truth, cycles = scenario_data
    pack_dir = write_pack(
        tmp_path / "pack",
        scenario="test_scenario",
        truth=truth,
        cycles=cycles,
        source={},
    )
    # flip one byte in the truth file
    path = pack_dir / TRUTH_NAME
    raw = bytearray(path.read_bytes())
    raw[-1] ^= 0xFF
    path.write_bytes(bytes(raw))
    with pytest.raises(ValueError, match="sha256 mismatch"):
        load_pack(pack_dir)
    # verify=False still loads (explicit override)
    truth_loaded, _ = load_pack(pack_dir, verify=False)
    assert truth_loaded["u10"].shape == truth["u10"].shape


def test_pack_missing_file(tmp_path, scenario_data):
    truth, cycles = scenario_data
    pack_dir = write_pack(
        tmp_path / "pack",
        scenario="test_scenario",
        truth=truth,
        cycles=cycles,
        source={},
    )
    (pack_dir / cycle_file_name(6.0)).unlink()
    with pytest.raises(FileNotFoundError, match="missing"):
        load_pack(pack_dir)
