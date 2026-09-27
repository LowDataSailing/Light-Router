"""Operational passage simulation on real data: Canaries -> Cape Verde.

A real router at sea does not sail its forecast: every 6 h (00/06/12/18Z)
it receives a new forecast package — degraded to its bandwidth budget —
replans from its current position, and the boat then advances on whatever
the weather actually does. This example mimics that, virtually, for a past
passage (September 2025, Canary Islands -> Sal, Cape Verde):

- truth: ERA5 reanalysis (measured weather) via the Open-Meteo archive
  API, on the absolute passage clock;
- forecasts: the GFS runs actually issued during the passage (NOAA AWS
  historical archive, wind messages only via range requests), one every
  6 h, each degraded to the budget before the router sees it;
- the boat follows each plan at the speed the *true* wind allows.

The whole passage is one experiment: passage time vs the unlimited-data
reference is the bandwidth-quality cost, this time with the
forecast-vs-reality gap a real router experiences.

Usage:
    uv run python examples/operational_passage.py               # real data
    uv run python examples/operational_passage.py --artifacts  # + run directory
    uv run python examples/operational_passage.py --start-date 2025-09-01 \
        --budgets unlimited,100000,10000,5000,2000,1000

GRIB loading needs the ``grib`` dependency group and a system ecCodes
library (Debian: ``apt install libeccodes0``). Downloads are cached under
data/cache/ — re-runs are free.
"""

from __future__ import annotations

import argparse
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from light_router.artifacts import (  # noqa: E402
    new_run_dir,
    write_operational_artifacts,
)
from light_router.data.era5 import fetch_era5_wind_grid  # noqa: E402
from light_router.data.gfs_archive import download_gfs_archive_wind  # noqa: E402
from light_router.grib import load_grib_wind  # noqa: E402
from light_router.isochrone import RouterConfig  # noqa: E402
from light_router.polar import synthetic_cruising_polar  # noqa: E402
from light_router.simulate import (  # noqa: E402
    ForecastCycle,
    format_operational_summary,
    run_operational_staircase,
)
from light_router.weather import route_grid_box  # noqa: E402

START = (28.0, -15.5)  # Canary Islands
FINISH = (16.75, -22.9)  # Sal, Cape Verde
CACHE = Path(__file__).resolve().parents[1] / "data" / "cache"
RUNS = Path(__file__).resolve().parents[1] / "runs"

FORECAST_HOURS = list(range(0, 121, 3))  # each cycle's 120 h horizon
TRUTH_STEP_DEG = 0.5
DEFAULT_BUDGETS = "unlimited,100000,10000,5000,2000,1000"


def parse_budgets(text: str) -> list[int | None]:
    """Parse a comma-separated budget list ("unlimited" or bytes)."""
    budgets: list[int | None] = []
    for item in text.split(","):
        item = item.strip()
        if item.lower() in ("unlimited", "none"):
            budgets.append(None)
        else:
            budgets.append(int(item))
    return budgets


def era5_truth(start: date, days: int, extent: tuple[float, float, float, float]):
    """Measured-weather grid on the absolute passage clock (hours since start)."""
    lon_min, lon_max, lat_min, lat_max = extent
    lats = np.arange(lat_min, lat_max + TRUTH_STEP_DEG / 2, TRUTH_STEP_DEG)
    lons = np.arange(lon_min, lon_max + TRUTH_STEP_DEG / 2, TRUTH_STEP_DEG)
    start_str = start.strftime("%Y-%m-%d")
    end = start + timedelta(days=days)
    cache = CACHE / f"era5_{start_str}_{end.strftime('%Y-%m-%d')}.json"
    print(
        f"ERA5 truth: {len(lats)}x{len(lons)} points, "
        f"{start_str}..{end.strftime('%Y-%m-%d')} ({days * 24} h)"
    )
    return fetch_era5_wind_grid(
        lats,
        lons,
        start_date=start_str,
        end_date=end.strftime("%Y-%m-%d"),
        cache_path=cache,
    )


def gfs_cycles(
    start: date, days: int, extent: tuple[float, float, float, float], workers: int
) -> list[ForecastCycle]:
    """The GFS runs issued during the passage, one per 6 h cycle."""
    cycles: list[ForecastCycle] = []
    for day in range(days + 1):
        for hour in ("00", "06", "12", "18"):
            rundate = (start + timedelta(days=day)).strftime("%Y%m%d")
            init_hour = day * 24 + int(hour)
            print(f"GFS run {rundate}/{hour}Z (cycle hour {init_hour})...", flush=True)
            paths = download_gfs_archive_wind(
                rundate, hour, FORECAST_HOURS, CACHE, workers=workers
            )
            weather = load_grib_wind(paths, extent=extent)
            cycles.append(ForecastCycle(init_hour=init_hour, weather=weather))
    return cycles


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--start-date", default="2025-09-01", help="passage start (UTC)"
    )
    parser.add_argument(
        "--days",
        type=int,
        default=7,
        help="days of truth/cycles to fetch (covers the passage horizon)",
    )
    parser.add_argument("--budgets", default=DEFAULT_BUDGETS)
    parser.add_argument("--workers", type=int, default=8, help="parallel downloads")
    parser.add_argument(
        "--artifacts",
        action="store_true",
        help="write a run directory (manifest, GPX/GeoJSON tracks, plots)",
    )
    args = parser.parse_args()

    start = datetime.strptime(args.start_date, "%Y-%m-%d").date()
    budgets = parse_budgets(args.budgets)
    extent = route_grid_box(START, FINISH, margin_deg=4.0)

    truth = era5_truth(start, args.days, extent)
    cycles = gfs_cycles(start, args.days, extent, args.workers)
    print(
        f"truth: {truth.sizes['time']} steps, "
        f"{truth.sizes['latitude']}x{truth.sizes['longitude']}; "
        f"{len(cycles)} forecast cycles"
    )

    router_config = RouterConfig(
        dt_hours=1.0,
        n_headings=36,
        bin_deg=0.5,
        max_points=1200,
        finish_radius_nm=25.0,
        max_hours=120.0,  # each cycle's forecast horizon
    )
    results = run_operational_staircase(
        truth,
        cycles,
        START,
        FINISH,
        synthetic_cruising_polar(),
        budgets,
        router_config,
        cycle_hours=6.0,
        dt_hours=1.0,
        finish_radius_nm=25.0,
        max_hours=240.0,
    )

    print(format_operational_summary(results))

    if args.artifacts:
        run_dir = new_run_dir(RUNS, scenario="operational_canaries_cv")
        write_operational_artifacts(
            run_dir,
            results,
            truth,
            scenario="operational_canaries_cv",
            start=START,
            finish=FINISH,
            router_config=router_config,
            budgets=budgets,
            source={
                "type": "operational",
                "truth": "ERA5 (Open-Meteo archive API)",
                "forecasts": "GFS 0.25 deg (NOAA AWS archive)",
                "start_date": args.start_date,
                "cycle_hours": 6,
            },
        )
        print(f"\nartifacts written to {run_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
