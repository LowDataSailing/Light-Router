"""Goal 1 demo: the bandwidth-quality degradation curve, end to end.

Usage:
    uv run python examples/degradation_curve.py --source synthetic
    uv run python examples/degradation_curve.py --source gfs --rundate 20260926

Scenario: open-ocean trade wind, Canary Islands -> Cape Verde (no land
avoidance, single planning-time forecast — see specs/goal-1-baseline.md).

Outputs examples/output/degradation_curve.csv and prints a summary table.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from light_router.data.gfs import download_gfs_wind  # noqa: E402
from light_router.grib import load_grib_wind  # noqa: E402
from light_router.isochrone import IsochroneRouter, RouterConfig  # noqa: E402
from light_router.polar import synthetic_cruising_polar  # noqa: E402
from light_router.staircase import run_staircase, write_csv  # noqa: E402
from light_router.synthetic import trade_wind_field  # noqa: E402
from light_router.weather import WeatherGrid  # noqa: E402

START = (28.0, -15.5)  # Canary Islands
FINISH = (16.75, -22.9)  # Sal, Cape Verde
CACHE = Path(__file__).resolve().parents[1] / "data" / "cache"
OUTPUT = Path(__file__).resolve().parents[1] / "examples" / "output"


def synthetic_grid() -> WeatherGrid:
    lats = np.arange(12.0, 32.01, 0.25)
    lons = np.arange(-26.0, -12.99, 0.25)
    times = np.arange(0.0, 121.0, 3.0)
    field = trade_wind_field(
        lats, lons, times, mean_speed_kt=15.0, direction_from_deg=30.0
    )
    # spatial structure + a pulsing storm on the direct route, so the curve
    # shows a real bandwidth-quality tradeoff (a uniform field compresses to
    # a few KB at full fidelity and degrades for free)
    factor = 1.0 + 0.5 * (lats - lats[0]) / (lats[-1] - lats[0])
    wave = 1.0 + 0.25 * np.sin(lons[None, :] * 4.0) * np.sin(lats[:, None] * 6.0)
    modulation = (factor[:, None] * wave)[None, :, :]
    for name in ("u10", "v10"):
        field.data[name] = (field.data[name] * modulation).astype(np.float32)
    d = np.sqrt((lats[:, None] - 22.5) ** 2 + (lons[None, :] + 19.0) ** 2)
    mask = np.exp(-((d / 2.5) ** 2))
    pulse = 0.5 + 0.5 * np.sin(2 * np.pi * times / 36.0)
    storm = (mask[None, :, :] * pulse[:, None, None]).astype(np.float32)
    for name in ("u10", "v10"):
        field.data[name] = ((1.0 - storm) * field.data[name] + storm * 15.0).astype(
            np.float32
        )
    return field


def gfs_grid(rundate: str, run_hour: str) -> WeatherGrid:
    paths = download_gfs_wind(
        rundate=rundate,
        run_hour=run_hour,
        forecast_hours=list(range(0, 121, 3)),
        lon_min=-27.0,
        lon_max=-12.0,
        lat_min=12.0,
        lat_max=32.0,
        cache_dir=CACHE,
    )
    return load_grib_wind(paths)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", choices=["synthetic", "gfs"], default="synthetic")
    parser.add_argument("--rundate", default="20260926")
    parser.add_argument("--run-hour", default="00")
    args = parser.parse_args()

    grid = (
        synthetic_grid()
        if args.source == "synthetic"
        else gfs_grid(args.rundate, args.run_hour)
    )
    print(
        f"weather grid: {len(grid.times)} steps, {len(grid.lats)}x{len(grid.lons)} "
        f"({grid.grid_extent()[0]:.1f}E..{grid.grid_extent()[1]:.1f}E, "
        f"{grid.grid_extent()[2]:.1f}N..{grid.grid_extent()[3]:.1f}N)"
    )

    router = IsochroneRouter(
        grid=grid,
        polar=synthetic_cruising_polar(),
        config=RouterConfig(
            dt_hours=1.0,
            n_headings=36,
            bin_deg=0.5,
            max_points=1200,
            finish_radius_nm=25.0,
            max_hours=150.0,
        ),
    )
    rows = run_staircase(grid, router, START, FINISH)

    out = OUTPUT / "degradation_curve.csv"
    write_csv(rows, out)

    print(
        f"\n{'budget':>10} {'bytes':>9} {'s/t/b':>10} {'ETA diff':>9} "
        f"{'dist diff':>9} {'VMG diff':>8} {'decision':>8} {'geo div':>8}"
    )
    for row in rows:
        m = row.metrics
        eta = f"{m.eta_diff_pct:+.1f}%" if m.reached else "n/a"
        print(
            f"{row.budget:>10} {row.package_bytes:>9} "
            f"{row.spatial_stride}/{row.temporal_stride}/{row.bits:>2}   "
            f"{eta:>9} {m.distance_diff_pct:+7.1f}% {m.vmg_diff_kt:+7.2f} "
            f"{str(m.decision_divergence):>8} {m.geographic_divergence_nm:7.1f}nm"
        )
    print(f"\nCSV written to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
