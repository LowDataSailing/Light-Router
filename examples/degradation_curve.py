"""Goal 1 demo: the bandwidth-quality degradation curve, end to end.

Usage:
    uv run python examples/degradation_curve.py --source synthetic
    uv run python examples/degradation_curve.py --source gfs --rundate 20260926

Scenario: open-ocean trade wind, Canary Islands -> Cape Verde (no land
avoidance, single planning-time forecast — see specs/goal-1-baseline.md).

Weather flows through the canonical CF xarray Dataset (Compatibility rule
1) and routing goes through a Router factory (rule 2): the in-repo
isochrone surrogate below is swappable for an external oracle without
touching this script.

Outputs examples/output/degradation_curve.csv and prints a summary table.
With --artifacts, also writes a run directory runs/<scenario>/<ts>-<sha>/
(manifest, GPX/GeoJSON routes, metrics.csv, plots) — see
specs/goal-1-baseline.md section 7.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import xarray as xr

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from light_router.artifacts import new_run_dir, write_artifacts  # noqa: E402
from light_router.data.gfs import download_gfs_wind  # noqa: E402
from light_router.data.gfs_archive import download_gfs_archive_wind  # noqa: E402
from light_router.dataset import dataset_extent, to_cf_dataset  # noqa: E402
from light_router.grib import load_grib_wind  # noqa: E402
from light_router.isochrone import RouterConfig  # noqa: E402
from light_router.polar import synthetic_cruising_polar  # noqa: E402
from light_router.scenario import Scenario, surrogate_router_factory  # noqa: E402
from light_router.staircase import STAIRCASE, format_summary, write_csv  # noqa: E402
from light_router.synthetic import add_storm, trade_wind_field  # noqa: E402
from light_router.weather import route_grid_box  # noqa: E402

START = (28.0, -15.5)  # Canary Islands
FINISH = (16.75, -22.9)  # Sal, Cape Verde
CACHE = Path(__file__).resolve().parents[1] / "data" / "cache"
OUTPUT = Path(__file__).resolve().parents[1] / "examples" / "output"
RUNS = Path(__file__).resolve().parents[1] / "runs"


def synthetic_weather() -> xr.Dataset:
    """Build the synthetic scenario weather as a canonical CF Dataset."""
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
    return to_cf_dataset(add_storm(field))


def gfs_weather(rundate: str, run_hour: str, archive: bool) -> xr.Dataset:
    """Download GFS wind for the route box and load it as a CF Dataset.

    ``archive`` fetches from the NOAA AWS historical archive (range-request
    wind messages only) instead of NOMADS — required for runs older than
    ~14 days.
    """
    lon_min, lon_max, lat_min, lat_max = route_grid_box(START, FINISH, margin_deg=4.0)
    forecast_hours = list(range(0, 121, 3))
    if archive:
        paths = download_gfs_archive_wind(rundate, run_hour, forecast_hours, CACHE)
    else:
        paths = download_gfs_wind(
            rundate=rundate,
            run_hour=run_hour,
            forecast_hours=forecast_hours,
            lon_min=lon_min,
            lon_max=lon_max,
            lat_min=lat_min,
            lat_max=lat_max,
            cache_dir=CACHE,
        )
    return load_grib_wind(paths, extent=(lon_min, lon_max, lat_min, lat_max))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", choices=["synthetic", "gfs"], default="synthetic")
    parser.add_argument("--rundate", default="20260926")
    parser.add_argument("--run-hour", default="00")
    parser.add_argument(
        "--archive",
        action="store_true",
        help="fetch from the NOAA AWS historical archive instead of NOMADS "
        "(needed for runs older than ~14 days)",
    )
    parser.add_argument(
        "--artifacts",
        action="store_true",
        help="write a run directory (manifest, GPX/GeoJSON routes, plots)",
    )
    args = parser.parse_args()

    weather = (
        synthetic_weather()
        if args.source == "synthetic"
        else gfs_weather(args.rundate, args.run_hour, args.archive)
    )
    lon_min, lon_max, lat_min, lat_max = dataset_extent(weather)
    print(
        f"weather dataset: {weather.sizes['time']} steps, "
        f"{weather.sizes['latitude']}x{weather.sizes['longitude']} "
        f"({lon_min:.1f}E..{lon_max:.1f}E, {lat_min:.1f}N..{lat_max:.1f}N)"
    )

    scenario = Scenario(weather=weather, start=START, finish=FINISH)
    router_config = RouterConfig(
        dt_hours=1.0,
        n_headings=36,
        bin_deg=0.5,
        max_points=1200,
        finish_radius_nm=25.0,
        max_hours=150.0,
    )
    factory = surrogate_router_factory(
        polar=synthetic_cruising_polar(),
        config=router_config,
    )
    result = scenario.run(factory)
    rows = result.rows

    out = OUTPUT / "degradation_curve.csv"
    write_csv(rows, out)

    print(format_summary(rows))
    print(f"\nCSV written to {out}")

    if args.artifacts:
        run_dir = new_run_dir(RUNS, scenario=f"{args.source}_canaries_cv")
        write_artifacts(
            run_dir,
            result,
            scenario.weather,
            scenario=f"{args.source}_canaries_cv",
            start=START,
            finish=FINISH,
            router_config=router_config,
            staircase=STAIRCASE,
            source={
                "type": args.source,
                "rundate": args.rundate,
                "run_hour": args.run_hour,
                "archive": args.archive,
            },
        )
        print(f"artifacts written to {run_dir}")
        print("re-render later with: uv run python -m light_router.summarize <run_dir>")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
