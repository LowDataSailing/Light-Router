import csv

import numpy as np
import pytest

from light_router.models.vessel import PolarTable, synthetic_cruising_polar


def test_polar_rejects_bad_shape():
    with pytest.raises(ValueError):
        PolarTable(
            tws=np.array([0.0, 10.0]), twa=np.array([0.0, 90.0]), speed=np.zeros((2, 3))
        )


def test_polar_interpolation_midpoint():
    table = PolarTable(
        tws=np.array([10.0, 20.0]),
        twa=np.array([0.0, 90.0]),
        speed=np.array([[0.0, 5.0], [0.0, 10.0]]),
    )
    assert table.boat_speed(15.0, 45.0) == pytest.approx(3.75)


def test_polar_tack_symmetry():
    table = synthetic_cruising_polar()
    assert table.boat_speed(12.0, 60.0) == pytest.approx(table.boat_speed(12.0, -60.0))
    assert table.boat_speed(12.0, 60.0) == pytest.approx(table.boat_speed(12.0, 300.0))


def test_polar_nogo_zone():
    table = synthetic_cruising_polar()
    assert table.boat_speed(12.0, 20.0) == pytest.approx(0.0, abs=1e-9)


def test_polar_clamps_beyond_table():
    table = synthetic_cruising_polar()
    assert table.boat_speed(100.0, 90.0) == pytest.approx(table.boat_speed(40.0, 90.0))


def test_synthetic_polar_shape():
    table = synthetic_cruising_polar()
    # best angle around a broad reach, not upwind
    speeds = [table.boat_speed(15.0, a) for a in (45.0, 90.0, 120.0, 180.0)]
    assert max(speeds) == speeds[2]
    # hull-speed plateau: 20 kt wind does not double the 10 kt speed
    assert table.boat_speed(20.0, 120.0) < 2.0 * table.boat_speed(10.0, 120.0)


def test_polar_csv_roundtrip(tmp_path):
    table = synthetic_cruising_polar()
    path = tmp_path / "polar.csv"
    table.to_polar_csv(path)
    loaded = PolarTable.from_polar_csv(path)
    assert np.allclose(loaded.tws, table.tws)
    assert np.allclose(loaded.twa, table.twa)
    assert np.allclose(loaded.speed, table.speed)
    assert loaded.boat_speed(15.0, 120.0) == pytest.approx(
        table.boat_speed(15.0, 120.0)
    )


def test_polar_csv_layout(tmp_path):
    path = tmp_path / "polar.csv"
    synthetic_cruising_polar().to_polar_csv(path)
    rows = list(csv.reader(path.read_text().splitlines()))
    # first row: header cell + TWS values
    assert len(rows[0]) == len(rows[1])
    # first column of data rows: TWA values
    assert float(rows[1][0]) == 0.0


def test_polar_csv_rejects_too_small(tmp_path):
    path = tmp_path / "bad.csv"
    path.write_text("only,one,row\n")
    with pytest.raises(ValueError, match="too small"):
        PolarTable.from_polar_csv(path)
